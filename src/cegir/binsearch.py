"""
Find upperbound of polynomials using binary search-CEGIR approach
"""
import math
import pdb
from time import time

import z3
import sage.all

import helpers.vcommon as CM
from helpers.miscs import Miscs

import settings
import data.traces
import data.poly.base
import data.poly.mp
import data.inv.mp
import data.inv.oct
import cegir.base

DBG = pdb.set_trace

mlog = CM.getLogger(__name__, settings.logger_level)


class CegirBinSearch(cegir.base.Cegir):
    ub = 'ub'

    def __init__(self, symstates, prog):
        super().__init__(symstates, prog)

    def gen(self, traces, inps):
        assert isinstance(traces, data.traces.DTraces) and traces, traces
        assert isinstance(inps, data.traces.Inps), inps

        locs = traces.keys()
        termss = [self.get_terms(self.inv_decls[loc].sageExprs)
                  for loc in locs]

        mlog.debug("check upperbounds for {} terms at {} locs".format(
            sum(map(len, termss)), len(locs)))
        maxV = settings.OCT_MAX_V
        minV = -1*maxV
        refs = {loc: {self.mk_le(t, maxV): t for t in terms}
                for loc, terms in zip(locs, termss)}
        ieqs = data.inv.invs.DInvs(
            [(loc, data.inv.invs.Invs(refs[loc].keys())) for loc in refs])

        cexs, ieqs = self.check(ieqs, inps=None)

        if cexs:
            cexs_inps = inps.merge(cexs, self.inp_decls.names)
            if cexs_inps:
                self.get_traces(cexs_inps, traces)

        ieqs = ieqs.remove_disproved()

        tasks = [(loc, refs[loc][mp]) for loc in ieqs for mp in ieqs[loc]]
        mlog.debug("{} locs: infer upperbounds for {} terms".format(
            len(locs), len(tasks)))

        def f(tasks):
            return [(loc,
                     self.gc(loc, term, minV, maxV, traces))
                    for loc, term in tasks]
        wrs = Miscs.run_mp('guesscheck', tasks, f)
        rs = [(loc, inv) for loc, inv in wrs if inv]
        dinvs = data.inv.invs.DInvs()
        for loc, inv in rs:
            dinvs.setdefault(loc, data.inv.invs.Invs()).add(inv)
        return dinvs

    def gc(self, loc, term, minV, maxV, traces):
        assert isinstance(term, data.poly.base.Poly)
        assert minV <= maxV, (minV, maxV)
        statsd = {maxV: data.inv.base.Inv.PROVED}

        # start with this minV
        vs = term.eval_traces(traces[loc])
        try:
            mymaxV = int(max(v for v in vs))
            if mymaxV > maxV:
                # occurs when checking above fails
                # (e.g., cannot show term <= maxV even though it is true)
                return None

            mminV = int(max(minV, mymaxV))
        except ValueError:
            mminV = minV

        # start with this maxV
        i = -1
        v = mminV
        while True:
            if i != -1:  # not first time
                v = mminV + 2**i

            if v >= maxV:
                break

            i = i + 1
            cexs, stat = self._mk_upp_and_check(loc, term, v)
            assert v not in statsd, v
            statsd[v] = stat

            if loc in cexs:  # disproved
                mminV = self._get_max_from_cexs(loc, term, cexs)
                if mminV >= maxV:
                    return None

            else:  # proved , term <= v
                break

        mmaxV = v if v < maxV else maxV
        mlog.debug("{}: compute ub for '{}', start with minV {}, maxV {}), {}"
                   .format(loc, term, mminV, mmaxV, mminV <= mmaxV))

        assert mminV <= mmaxV, (term, mminV, mmaxV)
        boundV = self.guess_check(loc, term, mminV, mmaxV, statsd)

        if (boundV is not None and
                (boundV not in statsd or statsd[boundV] != data.inv.base.Inv.DISPROVED)):
            stat = statsd[boundV] if boundV in statsd else None
            inv = self.mk_le(term, boundV)
            inv.stat = stat
            mlog.debug("got {}".format(inv))
            return inv
        else:
            return None

    def guess_check(self, loc, term, minV, maxV, statsd):
        assert isinstance(loc, str) and loc, loc
        assert isinstance(statsd, dict), statsd  # {v : proved}

        if minV > maxV:
            mlog.warning("{}: (guess_check) term {} has minV {} > maxV {}".format(
                loc, term, minV, maxV))
            return None  # temp fix

        if minV == maxV:
            return maxV
        elif maxV - minV == 1:
            if (minV in statsd and statsd[minV] == data.inv.base.Inv.DISPROVED):
                return maxV

            cexs, stat = self._mk_upp_and_check(loc, term, minV)
            assert minV not in statsd
            statsd[minV] = stat
            ret = maxV if loc in cexs else minV
            return ret

        v = (maxV + minV)/2.0
        v = int(math.ceil(v))

        cexs, stat = self._mk_upp_and_check(loc, term, v)
        assert v not in statsd, (term.term, minV, maxV, v, stat, statsd[v])
        statsd[v] = stat

        if loc in cexs:  # disproved
            minV = self._get_max_from_cexs(loc, term, cexs)
        else:
            maxV = v

        return self.guess_check(loc, term, minV, maxV, statsd)

    def get_terms(self, symbols):

        terms = []
        if settings.DO_IEQS:
            oct_siz = 2
            terms_ieqs = Miscs.get_terms_fixed_coefs(symbols, oct_siz)
            terms_ieqs = [data.poly.base.GeneralPoly(t) for t in terms_ieqs]
            terms.extend(terms_ieqs)

        if settings.DO_MINMAXPLUS:

            terms_u = data.poly.mp.MP.get_terms(symbols)
            terms_u_no_octs = [(a, b) for a, b in terms_u
                               if len(b) >= 2]

            if settings.DO_IEQS:  # ignore oct invs
                terms_u = terms_u_no_octs

            def _get_terms(terms_u, is_max):
                terms_l = [(b, a) for a, b in terms_u]
                terms = terms_u + terms_l
                terms = [data.poly.mp.MP(a, b, is_max) for a, b in terms]
                return terms

            terms_max = _get_terms(terms_u, is_max=True)

            terms_min = _get_terms(terms_u_no_octs, is_max=False)
            terms.extend(terms_min + terms_max)

        if settings.DO_TERM_FILTER:
            st = time()
            new_terms = self.filter_terms(
                terms, set(self.prog.inp_decls.names))
            Miscs.show_removed('term filter',
                               len(terms), len(new_terms), time() - st)
            return new_terms
        else:
            return terms

    @staticmethod
    def filter_terms(terms, inps):
        assert isinstance(inps, set) and \
            all(isinstance(s, str) for s in inps), inps

        if not inps:
            mlog.warning("Have not tested case with no inps")

        excludes = set()
        for term in terms:
            if isinstance(term, data.poly.mp.MP):
                a_symbs = list(map(str, Miscs.get_vars(term.a)))
                b_symbs = list(map(str, Miscs.get_vars(term.b)))
                inp_in_a = any(s in inps for s in a_symbs)
                inp_in_b = any(s in inps for s in b_symbs)

                if ((inp_in_a and inp_in_b) or
                        (not inp_in_a and not inp_in_b)):
                    excludes.add(term)
                    continue

                t_symbs = set(a_symbs + b_symbs)

            else:
                t_symbs = set(map(str, term.symbols))
                if len(t_symbs) <= 1:
                    continue

            assert len(t_symbs) > 1
            if (inps.issuperset(t_symbs) or
                    all(s not in inps for s in t_symbs)):
                excludes.add(term)

        new_terms = [term for term in terms if term not in excludes]
        return new_terms

    def mk_le(self, term, v):
        inv = term.mk_le(v)
        if isinstance(term, data.poly.base.GeneralPoly):
            inv = data.inv.oct.Oct(inv)
        else:
            inv = data.inv.mp.MP(inv)
        return inv

    def _mk_upp_and_check(self, loc, term, v):
        inv = self.mk_le(term, v)
        inv_ = data.inv.invs.DInvs.mk(loc, data.inv.invs.Invs([inv]))
        cexs, _ = self.check(
            inv_, inps=None, check_mode=self.symstates.check_validity)

        return cexs, inv.stat

    def _get_max_from_cexs(self, loc, term, cexs):
        mycexs = data.traces.Traces.extract(cexs[loc], useOne=False)
        return int(max(term.eval_traces(mycexs)))
