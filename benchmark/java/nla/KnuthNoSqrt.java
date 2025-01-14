public class KnuthNoSqrt {
	public static void vtrace1(int n, int a, int r, int k, int q, int d, int s, int t){}
	// public static void vtrace2(int n, int a, int r, int k, int q, int d, int s, int t){}
	public static void main (String[] args) {
	}
	
	public static int mainQ(int s, int a){
		//algorithm searching for a divisor for factorization, by Knuth
		assert(a > 2);
		assert(s >= 0);
		assert(s <= 30);
		
		int n,r,k,q,d,t;
		n = s*s;
		d=a;
		r= n % d;
		t = 0;
		k=n % (d-2);
		q=4*(n/(d-2) - n/d);
		
		
		while(true){
			//assert(d*d*q - 2*q*d - 4*r*d + 4*k*d  + 8*r == 8*n);
			//assert(k*t == t*t);
			//assert(d*d*q - 2*d*q - 4*d*r + 4*d*t + 4*a*k - 4*a*t - 8*n + 8*r == 0);
			//assert(d*k - d*t - a*k + a*t == 0);       
			vtrace1(n,a,r,k,q,d,s,t);
			if (!((s>=d)&&(r!=0))) break;
			
			if (2*r-k+q<0){
				t=r;
				r=2*r-k+q+d+2;
				k=t;
				q=q+4;
				d=d+2;
			} 
			else if ((2*r-k+q>=0)&&(2*r-k+q<d+2)){
				t=r;
				r=2*r-k+q;
				k=t;
				d=d+2;
			}
			else if ((2*r-k+q>=0)&&(2*r-k+q>=d+2)&&(2*r-k+q<2*d+4)){
				t=r;
				r=2*r-k+q-d-2;
				k=t;
				q=q-4;
				d=d+2;
			}
			else {/* ((2*r-k+q>=0)&&(2*r-k+q>=2*d+4)) */
				t=r;
				r=2*r-k+q-2*d-4;
				k=t;
				q=q-8;
				d=d+2;
			}
			
		}
		//vtrace2(n,a,r,k,q,d,s,t);
		return d;
	}
}
