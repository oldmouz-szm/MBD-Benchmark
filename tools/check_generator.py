#!/usr/bin/env python3
"""Independent arithmetic checks for gate libraries and small topology families."""
import random
from supplement import Circuit, ROOT, load_libraries, OFFSETS

def main():
    lib=load_libraries(ROOT/'library');rng=random.Random(783244)
    checked=0
    for name,g in lib.items():
        w=g.widths['a'];maximum=(1<<w)-1
        pairs=[(a,b) for a in (0,1,maximum,maximum//2) for b in (0,1,maximum,maximum//2)]
        pairs += [(rng.getrandbits(w),rng.getrandbits(w)) for _ in range(256)]
        for a,b in pairs:
            assert g.evaluate(a,b)[0]==g.arithmetic(a,b),(name,a,b)
            checked+=1
    topology_checks=0
    for family,size,w,count in [('ring',8,8,16),('ring',8,16,16),('mesh',3,8,36),('mesh',3,16,36),
                                ('cascade',8,8,24),('nonlocal_square',128,8,1280)]:
        c=Circuit(('check',family,size,w,count),lib)
        n=size*size if family=='mesh' else size
        for _ in range(16):
            aa=[rng.getrandbits(w) for _ in range(n)];bb=[rng.getrandbits(w) for _ in range(n)]
            inputs={p:sum(v<<(i*w) for i,v in enumerate(vals)) for p,vals in [('a',aa),('b',bb)]}
            t=[a+b for a,b in zip(aa,bb)]
            if family=='ring':ys=[t[i]*t[(i+1)%n] for i in range(n)]
            elif family=='mesh':
                ys=[t[r*size+j]*(t[r*size+(j+1)%size]+t[((r+1)%size)*size+j]) for r in range(size) for j in range(size)]
            elif family=='cascade':
                p=[a*b for a,b in zip(aa,bb)]
                ys=[p[(i+1)%n]*(p[i]+p[(i+2)%n]) for i in range(n)]
            else:ys=[t[i]*(t[i]+t[(i+k)%n]) for i in range(n) for k in OFFSETS]
            expected=sum(y<<(i*c.output_width) for i,y in enumerate(ys))
            assert c.simulate(inputs,all_gates=True)[0]['y']==expected
            topology_checks+=1
    print(dict(passed=True,library_vectors=checked,topology_vectors=topology_checks),flush=True)

if __name__=='__main__':main()
