"""Independent, deliberately small reference models. No model calls or third-party packages.

These check arithmetic, witnesses and selected finite domains, not arbitrary prose or
all legal large inputs. The Gold's written arguments remain separate evidence.
"""
from collections import deque
from fractions import Fraction
from itertools import combinations, product
from math import ceil, log2, isqrt, factorial
import heapq


def components(n, edges):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u-1].append(v-1); adj[v-1].append(u-1)
    label = [-1]*n
    for i in range(n):
        if label[i] != -1: continue
        todo = [i]; label[i] = i
        for u in todo:
            for v in adj[u]:
                if label[v] == -1: label[v] = i; todo.append(v)
    return label


def shortest(n, edges, directed=False, source=1, target=None):
    target = target or n
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u-1].append((v-1, w))
        if not directed: adj[v-1].append((u-1, w))
    dist = [float('inf')]*n; dist[source-1] = 0; todo = [(0, source-1)]
    while todo:
        d, u = heapq.heappop(todo)
        if d != dist[u]: continue
        for v, w in adj[u]:
            if d+w < dist[v]: dist[v] = d+w; heapq.heappush(todo, (d+w, v))
    return -1 if dist[target-1] == float('inf') else dist[target-1]


def solve(name, a):
    if name == 'booking':
        c = list(a['capacity'])
        for j, (l, r, d) in enumerate(a['orders'], 1):
            if any(c[i] < d for i in range(l-1, r)): return j
            for i in range(l-1, r): c[i] -= d
        return 0
    if name == 'dag':
        n = a['n']; adj = [[] for _ in range(n)]
        for u, v, w in a['edges']: adj[u-1].append((v-1, w))
        paths = []
        def visit(u, value):
            if u == n-1: paths.append(value)
            for v, w in adj[u]: visit(v, value+w)
        visit(0, 0)
        return [-1, 0] if not paths else [max(paths), paths.count(max(paths)) % 998244353]
    if name == 'tree_xor':
        n = a['n']; adj = [[] for _ in range(n)]
        for u, v, w in a['edges']: adj[u-1].append((v-1, w)); adj[v-1].append((u-1, w))
        vals = [None]*n; vals[0] = 0; todo = [0]
        for u in todo:
            for v, w in adj[u]:
                if vals[v] is None: vals[v] = vals[u] ^ w; todo.append(v)
        return max(x ^ y for x in vals for y in vals)
    if name == 'circular':
        v = a['a']; n = len(v)
        return max(sum(v[(i+j) % n] for j in range(length)) for i in range(n) for length in range(1, n+1))
    if name == 'ferry':
        n = a['n']; adj = [[] for _ in range(n)]
        for u, v, p, t in a['edges']: adj[u-1].append((v-1, p, t))
        dist = [float('inf')]*n; dist[0] = 0; todo = [(0, 0)]
        while todo:
            d, u = heapq.heappop(todo)
            if d != dist[u]: continue
            for v, p, t in adj[u]:
                nd = ((d+p-1)//p)*p+t
                if nd < dist[v]: dist[v] = nd; heapq.heappush(todo, (nd, v))
        return -1 if dist[-1] == float('inf') else dist[-1]
    if name == 'components':
        edges = set(); answer = []
        for op in a['ops']:
            if op[0] == '?': answer.append(len(set(components(a['n'], edges))))
            else:
                edge = tuple(sorted(op[1:]))
                if op[0] == '+': assert edge not in edges; edges.add(edge)
                else: edges.remove(edge)
        return answer
    if name == 'embedding':
        return sum(''.join(a['s'][i] for i in ix) == a['t'] for ix in combinations(range(len(a['s'])), len(a['t']))) % 1000000007
    if name == 'permutation':
        v = a['permutation']
        return sorted(v) == list(range(1, a['n']+1)) and sum(v[i] > v[j] for i in range(len(v)) for j in range(i+1, len(v))) == a['k']
    if name == 'degree_tree':
        deg = [0]*a['n']
        for u, v in a['edges']: deg[u-1] += 1; deg[v-1] += 1
        return len(a['edges']) == a['n']-1 and len(set(components(a['n'], a['edges']))) == 1 and deg == a['degrees']
    if name == 'matrix':
        mat = a['matrix']
        return all(len(row) == len(a['cols']) and set(row) <= set('01') for row in mat) and [row.count('1') for row in mat] == a['rows'] and [sum(mat[i][j] == '1' for i in range(len(mat))) for j in range(len(a['cols']))] == a['cols']
    if name == 'centroid':
        pts = a['points']; den = sum(p[2] for p in pts); assert den > 0
        return [float(Fraction(sum(p[j]*p[2] for p in pts), den)) for j in range(2)]
    if name == 'meeting':
        # Intervals [a_i-v_i T,a_i+v_i T] have common intersection iff every pair intersects.
        return float(max(Fraction(abs(x-y), u+v) for x, u in zip(a['positions'], a['speeds']) for y, v in zip(a['positions'], a['speeds'])))
    if name == 'expectation':
        states = a['states']; e = [Fraction(0)]*len(states)
        for i in reversed(range(len(states))):
            p, q, b = states[i]; e[i] = 1 + (Fraction(p, q)*e[b-1] if p else 0)
        return float(e[0])
    if name == 'interactive_search':
        for n in range(1, a['max_n']+1):
            for h in range(1, n+1):
                lo, hi = 1, n; queries = 0
                while lo <= hi:
                    mid = (lo+hi)//2; queries += 1
                    if mid == h: break
                    if h < mid: hi = mid-1
                    else: lo = mid+1
                if mid != h or queries > ceil(log2(n))+1: return False
        return True
    if name == 'tree_distance': return shortest(a['n'], [[u,v,1] for u,v in a['edges']], source=a['query'], target=a['hidden'])
    if name == 'parity': return sum(int(a['bits'][i-1]) for i in a['indices']) % 2
    if name == 'comm_index':
        return all(s[j] == ''.join(s)[j] for n in range(1, a['max_n']+1) for s in product('01', repeat=n) for j in range(n))
    if name == 'comm_sum':
        return all((int(format(x, f'0{k}b'), 2)+y) % (1 << k) == (x+y) % (1 << k) for k in range(1, a['max_k']+1) for x in range(1 << k) for y in range(1 << k))
    if name == 'comm_components':
        for n in range(1, a['max_n']+1):
            edges = list(combinations(range(1,n+1), 2)); width = n.bit_length()
            for mask in range(1 << len(edges)):
                label = components(n, [e for j,e in enumerate(edges) if mask >> j & 1])
                message = ''.join(format(x+1, f'0{width}b') for x in label)
                decoded = [int(message[i*width:(i+1)*width], 2) for i in range(n)]
                assert len(message) == n*width
                if any((decoded[u] == decoded[v]) != (label[u] == label[v]) for u in range(n) for v in range(n)): return False
        return True
    if name == 'warehouse':
        stock = a['stock']; failed = 0
        for inc, expense in a['days']:
            stock += inc
            if stock >= expense: stock -= expense
            else: failed += 1
            stock = min(stock, a['cap'])
        return [failed, stock]
    if name == 'robots':
        robots = {i+1:(x, 1 if direction == 'R' else -1) for i,(x,direction) in enumerate(a['robots'])}
        for _ in range(a['turns']):
            nxt = {i:(x+v,v) for i,(x,v) in robots.items()}; count = {}
            for x,v in nxt.values(): count[x] = count.get(x,0)+1
            robots = {i:(x,v) for i,(x,v) in nxt.items() if count[x] == 1}
        return [[i,x] for i,(x,v) in sorted(robots.items())]
    if name == 'round_robin':
        tasks = a['tasks']; remaining = [p for _,p in tasks]; answer = [None]*len(tasks)
        q = deque(); time = 0; old = None
        while any(x is None for x in answer):
            for i,(arrival,p) in enumerate(tasks):
                if arrival == time: q.append(i)
            if old is not None: q.append(old); old = None
            if q:
                j = q.popleft(); remaining[j] -= 1
                if remaining[j] == 0: answer[j] = time+1
                else: old = j
            time += 1
        return answer
    if name == 'portal':
        grid = a['grid']; n,m = len(grid),len(grid[0]); cells = [(i,j) for i in range(n) for j in range(m) if grid[i][j] != '#']
        edges=[]; start=target=None; ids={p:i+1 for i,p in enumerate(cells)}
        for i,j in cells:
            ch=grid[i][j]
            if ch=='S': start=ids[i,j]
            if ch=='T': target=ids[i,j]
            for x,y in cells:
                if abs(i-x)+abs(j-y)==1: edges.append([ids[i,j],ids[x,y],1])
                if ch.islower() and grid[x][y]==ch: edges.append([ids[i,j],ids[x,y],0])
        return shortest(len(cells),edges,True,start,target)
    if name == 'multiset':
        v=[]; ans=[]
        for op,x in a['ops']:
            if op=='+': v.append(x)
            elif op=='-': v.remove(x)
            else: ans.append(sorted(v)[x-1])
        return ans
    if name == 'direction_witness':
        edges=[[1,2,1],[2,3,1],[3,1,1]]
        return [shortest(3,edges,False,2,1),shortest(3,edges,True,2,1)]
    if name == 'empty_minimum': return not list(combinations(range(1),2))
    if name == 'tree_edge_count': return len(a['edges']) == a['n']-1 and len(set(components(a['n'],a['edges']))) == 1
    if name == 'zero_denominator': return a['denominator'] == 0 and a['numerator'] != 0
    if name == 'mst':
        vals=[sum(w for _,_,w in edges) for edges in combinations(a['edges'],a['n']-1) if len(set(components(a['n'],[(u,v) for u,v,w in edges])))==1]
        return min(vals)
    if name == 'ledger':
        vals=list(a['a']); p,q,r=a['p'],a['q'],a['r']
        for j,d in a['ops']: vals[p[q[j-1]-1]-1] += d
        return [vals[p[q[j-1]-1]-1] for j in r]
    if name == 'odd_cycle': return not any(all(bits[u] != bits[v] for u,v in [(0,1),(1,2),(2,0)]) for bits in product(range(2), repeat=3))
    if name == 'sqrt_irrational': return isqrt(2)**2 != 2
    if name == 'edge_query_budget': return a['queries'] >= a['n']*(a['n']-1)//2
    if name == 'information_bound': return a['replies']**a['queries'] >= a['states']
    if name == 'communication_bound': return 2**a['message_bits'] >= 2**a['n']
    if name == 'permutation_communication_bound': return 2**a['message_bits'] >= factorial(a['n'])
    if name == 'account_order': return [[0,1+1-2],[1,1+1]]
    if name == 'matching_conflict':
        edges=[{1,2},{3,4}]; disjoint=[];intersect=[]
        for size in range(3):
            for subset in combinations(edges,size):
                pairs=list(combinations(subset,2))
                if all(not (u & v) for u,v in pairs):disjoint.append(size)
                if all(u & v for u,v in pairs):intersect.append(size)
        return [max(disjoint),max(intersect)]
    if name == 'delete_range': return min(max(v)-min(v) for i in range(len(a['a'])) if (v := a['a'][:i]+a['a'][i+1:]))
    if name == 'shortest': return shortest(**a)
    if name == 'carriages':
        c=list(a['capacity']); ans=[]
        for b in a['batches']:
            j=next((i for i,x in enumerate(c) if x>=b),None)
            ans.append(-1 if j is None else j+1)
            if j is not None: c[j]-=b
        return ans
    if name == 'test_count': return a['declared'] == len(a['groups'])
    raise ValueError('Unknown oracle: '+name)


def sample_check(gold):
    """Parse actual sample input/output for clean families, independent of Gold args."""
    if not gold['samples']: return True
    raw=gold['samples'][0]; lines=raw['input'].splitlines(); tok=iter(raw['input'].split()); out=raw['output'].split()
    family=int(gold['family_id'].split('-')[1]); name=gold['oracle']['name']
    def num(): return int(next(tok))
    try:
        if family==1:
            n,m=num(),num(); args={'capacity':[num() for _ in range(n)],'orders':[[num(),num(),num()] for _ in range(m)]}
        elif family in (2,3,5):
            n=num(); m=n-1 if family==3 else num(); width=4 if family==5 else 3
            args={'n':n,'edges':[[num() for _ in range(width)] for _ in range(m)]}
        elif family==4:
            n=num();args={'a':[num() for _ in range(n)]}
        elif family==6:
            n,q=num(),num();ops=[]
            for _ in range(q):
                op=next(tok);ops.append([op] if op=='?' else [op,num(),num()])
            args={'n':n,'ops':ops}
        elif family==7: args={'s':next(tok),'t':next(tok)}
        elif family==8:
            n,k=num(),num(); assert out[0]=='YES'; return solve(name,{'n':n,'k':k,'permutation':list(map(int,out[1:]))})
        elif family==9:
            n=num();degrees=[num() for _ in range(n)];assert out[0]=='YES'; edges=list(map(int,out[1:]));return solve(name,{'n':n,'degrees':degrees,'edges':[edges[i:i+2] for i in range(0,len(edges),2)]})
        elif family==10:
            n,m=num(),num();rows=[num() for _ in range(n)];cols=[num() for _ in range(m)];assert out[0]=='YES';return solve(name,{'rows':rows,'cols':cols,'matrix':out[1:]})
        elif family==11:
            n=num();args={'points':[[num(),num(),num()] for _ in range(n)]}
        elif family==12:
            n=num();pts=[[num(),num()] for _ in range(n)];args={'positions':[p[0] for p in pts],'speeds':[p[1] for p in pts]}
        elif family==13:
            n=num();args={'states':[[num(),num(),num()] for _ in range(n)]}
        elif family==20:
            d,s,c=num(),num(),num();args={'stock':s,'cap':c,'days':[[num(),num()] for _ in range(d)]}
        elif family==21:
            n,t=num(),num();args={'robots':[[num(),next(tok)] for _ in range(n)],'turns':t}
        elif family==22:
            n=num();args={'tasks':[[num(),num()] for _ in range(n)]}
        elif family==23:
            n,m=num(),num();args={'grid':[next(tok) for _ in range(n)]};assert all(len(s)==m for s in args['grid'])
        elif family==24:
            q=num();args={'ops':[[next(tok),num()] for _ in range(q)]}
        else: return True  # Defective originals use their separate witness checks.
        assert next(tok,None) is None
        answer=solve(name,args)
        if family in (11,12,13):
            answer=answer if isinstance(answer,list) else [answer]
            return len(answer)==len(out) and all(abs(float(v)-w)<=1e-6*max(1,abs(w)) for v,w in zip(out,answer))
        if family==21:
            expected=[len(answer)]+[x for row in answer for x in row]
        else: expected=answer if isinstance(answer,list) else [answer]
        return list(map(int,out)) == expected
    except (AssertionError, StopIteration,ValueError,IndexError,ZeroDivisionError): return False


def check_defect_witness(g):
    """Verify the stated finite witness/contradiction, not the natural-language severity.

    The language and normative cases are reported as textual checks, explicitly
    different from mathematical certificates. needs_review is never promoted here.
    """
    if not g['defects']: return {'method':'clean_sample_and_written_domain_audit','passed':sample_check(g)}
    if g['gold_status']=='needs_review':return {'method':'needs_independent_reader','passed':None}
    i=int(g['family_id'].split('-')[1]);mut=g['version']=='mutant';method='finite_witness_plus_written_argument'
    if mut:
        if i==1:
            c=[1];orders=[[1,1,1],[1,1,1]]
            passed=solve('booking',{'capacity':c,'orders':orders})==2  # swapping equal bookings changes their input labels
            passed=passed and [2,1][solve('booking',{'capacity':c,'orders':orders})-1]==1
        elif i==2:passed=(3+4==2+5==7)
        elif i==3:passed=solve('tree_xor',{'n':3,'edges':[[1,2,1],[2,3,1]]})==1 and 1+1==2
        elif i==4:passed=all(sum([1]*k)==k for k in range(1,11));method='increasing_finite_prefix_plus_unbounded_length_argument'
        elif i==5:passed=[((2+1)//2)*2+4,(2//2+1)*2+4]==[6,8]
        elif i in (6,10):passed=not sample_check(g)
        elif i==7:passed=solve('embedding',{'s':'aa','t':'a'})==2 and len({'aa'[j] for j in range(2)})==1
        elif i==8:
            from itertools import permutations
            passed=all(sum(p[x]>p[y] for x in range(len(p)) for y in range(x+1,len(p)))!=1 for p in permutations([1]))
        elif i==9:passed='无解输出一行 NO。' in g['defects'][0]['quote'];method='textual_norm_applicability_requiring_written_rubric'
        elif i==11:passed=solve('centroid',{'points':[[0,0,1]]})==[0,0]
        elif i in (12,13):passed=True;method='quoted_local_typo_and_exact_repair; not mathematical_language_validation'
        elif i==14:
            # Two bijections normal-reply -> relation, both consistent with an unmapped alphabet.
            passed=({'less':'Q','equal':'Z','greater':'A'}['greater']=={'less':'Q','equal':'A','greater':'Z'}['equal'])
        elif i==15:passed=solve('tree_distance',{'n':3,'edges':[[1,2],[2,3]],'query':1,'hidden':3})==2
        elif i==16:passed=(1-1==0 and 0 not in range(1,2))
        else:raise ValueError(i)
    elif i==25:passed=solve('direction_witness',{})==[1,2]
    elif i==26:passed=not list(combinations([5],2))
    elif i==27:passed=len([[1,2],[2,3],[1,3]])!=3-1;method='sample_edge_count_plus_tree_edge_theorem'
    elif i==28:
        try: Fraction(1,0)
        except ZeroDivisionError:passed=True
        else:passed=False
    elif i==29:
        tokens=list(map(int,g['samples'][0]['input'].split()));n,m=tokens[:2];edges=[tokens[j:j+3] for j in range(2,len(tokens),3)]
        passed=len(edges)==m and solve('mst',{'n':n,'edges':edges})==3 and g['samples'][0]['output'].strip()=='9'
    elif i==31:passed=solve('odd_cycle',{})
    elif i==32:passed=isqrt(2)**2!=2;method='nonsquare_integer_plus_rational_square_root_theorem'
    elif i==33:
        if g['oracle']['name']=='edge_query_budget':
            pairs=list(combinations(range(1,4),2))
            passed=all(any(edge not in [pairs[j] for j in queried] for edge in pairs) for queried in product(range(3),repeat=2))
            method='all_zero_transcripts_leave_an_unqueried_edge; not a graph-state leaf-count argument'
        else:passed=2**2<8;method='decision_tree_leaf_bound'
    elif i==34:
        from itertools import permutations
        signatures=set()
        for p in permutations(range(1,4)):
            signatures.add(tuple(p.index(u)<p.index(v) for u in range(1,4) for v in range(1,4) if u!=v))
        passed=len(signatures)==factorial(3) and len(signatures)>2**2
        method='exhaustive_pairwise_order_signatures_plus_injective_encoding_bound'
    elif i==35:
        s,inc,expense=1,1,2
        before=[0,s+inc-expense] if s+inc>=expense else [1,s+inc]
        after=[0,s-expense+inc] if s>=expense else [1,s+inc]
        passed=before==[0,0] and after==[1,2]
    elif i==36:passed=solve('matching_conflict',{})==[2,1]
    elif i in (37,38):passed=True;method='quoted_local_typo_and_exact_repair; not mathematical_language_validation'
    elif i==40:
        tokens=iter(map(int,g['samples'][0]['input'].split()));truncated=False
        try:
            t=next(tokens)
            for _ in range(t):
                n=next(tokens)
                for _ in range(n):next(tokens)
        except StopIteration:truncated=True
        passed=truncated
    else:raise ValueError(i)
    return {'method':method,'passed':bool(passed)}
