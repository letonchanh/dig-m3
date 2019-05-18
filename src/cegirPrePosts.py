import itertools
import vcommon as CM
from cegir import Cegir
from ds import Inps, Traces, DTraces, Inv, Invs, DInvs, PrePostInv
import sage.all
import z3
from miscs import Miscs, Z3
import settings
import pdb
trace = pdb.set_trace

mlog = CM.getLogger(__name__, settings.logger_level)


class CegirPrePosts(Cegir):
    def __init__(self, symstates, prog):
        super(CegirPrePosts, self).__init__(symstates, prog)

    @property
    def preconds(self):
        symbols = self.symstates.inp_decls.sageExprs
        siz = 2
        # terms = Miscs.get_terms_fixed_coefs(symbols, siz)
        # terms = [t <= 0 for t in terms]
        # return terms
        t1 = [t == 0 for t in symbols]  # M=0, N=0
        # M==N
        t2 = [x == y for x, y in itertools.combinations(symbols, siz)]
        # +/M+/-N >0
        t3 = [t < 0 for t in Miscs.get_terms_fixed_coefs(symbols, siz)]
        #t4 = [t <= 0 for t in Miscs.get_terms_fixed_coefs(symbols, siz)]
        return t1 + t2 + t3

    def gen(self, dinvs, traces):
        assert isinstance(dinvs, DInvs), dinvs
        assert isinstance(traces, DTraces), traces

        dinvs_ = DInvs()
        cache = {}
        for loc in dinvs:
            if settings.POST_LOC not in loc:
                continue

            for inv in dinvs[loc]:
                if not inv.is_eq:
                    continue
                if inv in cache:
                    preposts = cache[inv]
                else:
                    disjss = self.get_disjs(inv.inv)
                    print(disjss)
                    preposts = self.get_preposts(loc, disjss, traces)
                    print(preposts)
                    cache[inv] = preposts

                if preposts:
                    if loc not in dinvs_:
                        dinvs_[loc] = Invs()
                    for prepost in preposts:
                        dinvs_[loc].add(prepost)

        return dinvs_

    def get_preposts(self, loc, disjss, traces):
        mydisjs = [disj for disjs in disjss for disj in disjs]

        def toZ3(x):
            return Z3.toZ3(x, self.symstates.use_reals, useMod=False)

        print 'preconds', self.preconds
        preposts = []  # results
        for disj in mydisjs:
            print 'mydisj', disj
            tcs = [t for t in traces[loc] if t.test(disj)]
            print tcs
            preconds = [c for c in self.preconds
                        if all(t.test(c) for t in tcs)]
            print 'mypreconds', preconds

            if not preconds:
                continue

            precond = [toZ3(c) for c in
                       Z3.reduceSMT(preconds, self.symstates.use_reals)]
            inv = z3.Implies(z3.And(precond), toZ3(disj))

            _, cexs, isSucc = self.symstates.mcheckD(
                loc, pathIdx=None, inv=inv, inps=None)

            if cexs or not isSucc:
                mlog.warn("{}: remove spurious result {}".format(loc, inv))

            preconds = [Inv(c) for c in preconds]
            prepost = PrePostInv(disj, Invs(preconds))
            preposts.append(prepost)

        return preposts

    def get_disjs(self, eqt):
        symbols = Miscs.getVars(eqt)  # x,y,z

        # if special symbols, e.g., tCtr, exist, then only consider those
        symbols_ = [s for s in symbols if settings.CTR_VAR in str(s)]
        if symbols_:
            assert len(symbols_) == 1
            symbols = symbols_

        disjss = [sage.all.solve(eqt, s) for s in symbols]
        # len(disjs) >= 2 indicate disj, e.g., x^2 = 1 -> [x=1,x=-1]
        disjss = [disjs for disjs in disjss if len(disjs) >= 2]
        return disjss
