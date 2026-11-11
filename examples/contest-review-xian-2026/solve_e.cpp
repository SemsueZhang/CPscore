#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <unordered_map>
#include <utility>
#include <vector>
using namespace std;
using U=uint64_t;
#ifndef CP_BLOCK_SIZE
#define CP_BLOCK_SIZE 1800
#endif
int pc(U x){return __builtin_popcountll(x);}
int bit(U x){return __builtin_ctzll(x);}
#ifdef CP_RANDOM_SEED
mt19937_64 gen(CP_RANDOM_SEED);
#else
mt19937_64 gen(random_device{}());
#endif
int pick(int n){return uniform_int_distribution<int>(0,n-1)(gen);}
struct Hash{size_t operator()(U x)const{static const U salt=gen();x+=salt+0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}};
struct DSU {
 struct Node{int p,rank,cnt;U value;};vector<Node> t;
 int make(U v,int count){int u=t.size();t.push_back({u,0,count,v});return u;}
 int find(int u){int r=u;while(t[r].p!=r)r=t[r].p;while(t[u].p!=u){int v=t[u].p;t[u].p=r;u=v;}return r;}
 int merge(int a,int b,U x){a=find(a);b=find(b);if(a==b)return a;if(t[a].rank<t[b].rank)swap(a,b);t[b].p=a;t[a].cnt+=t[b].cnt;t[a].value=x;if(t[a].rank==t[b].rank)t[a].rank++;return a;}
} dsu;
struct Block {
 int size,P=1,A=-1,B=-1,delta=0;U av=0,bv=0,sum=0,D=0,reserve=0;
 vector<int> ids,active,pos,freeSlots,far,fpos,roots;
 vector<U> values;unordered_map<U,int,Hash> byValue;
 array<U,64> adj{};array<int,64> degree{};int edges=0;U singles=0,used=0;
 array<int,64> which{};vector<U> variable,constant;vector<int> constCode,dBits;
 vector<array<U,7>> tree;bool removedA=false,removedB=false;
 explicit Block(const vector<U>& data):size(data.size()),pos(size,-1),fpos(size,-1),roots(size),values(size){
  byValue.reserve(size*2);
  for(int i=size-1;i>=0;i--)freeSlots.push_back(i);
  for(U v:data){auto it=byValue.find(v);int r;if(it==byValue.end()){r=dsu.make(v,0);insertClass(v,r);}else r=roots[it->second];dsu.t[r].cnt++;ids.push_back(r);sum+=v;}
  A=active[pick(active.size())];rebuildAll();
 }
 int insertClass(U v,int root){int s=freeSlots.back();freeSlots.pop_back();values[s]=v;roots[s]=root;pos[s]=active.size();fpos[s]=-1;active.push_back(s);byValue[v]=s;return s;}
 void graph(U e,bool add){
  int k=pc(e);if(k==1){if(add)singles|=e;else singles&=~e;}
  if(k==2){int u=bit(e);e&=e-1;int v=bit(e);U a=1ULL<<u,b=1ULL<<v;
   if(add){adj[u]|=b;adj[v]|=a;degree[u]++;degree[v]++;edges++;used|=a|b;}
   else{adj[u]&=~b;adj[v]&=~a;degree[u]--;degree[v]--;edges--;if(!degree[u])used&=~a;if(!degree[v])used&=~b;}
  }
 }
 array<U,7> maskFor(U v)const{
  array<U,7> out{};U E=v^av;
  for(int i=0;i<(int)variable.size();i++){
   int h=pc(E^variable[i]);U z=h<=2?~D:(h<=4?(E&~D):0);if(h<=3)z|=reserve;out[i]=z;
  }
  for(int i=0;i<(int)constant.size();i++)if(pc(E^constant[i])<=3)out[6]|=1ULL<<constCode[i];
  return out;
 }
 void point(int index,const array<U,7>& value){
  if(B<0||delta>6)return;
  int u=P+index;tree[u]=value;
  for(u/=2;u;u/=2)for(int j=0;j<7;j++)tree[u][j]=tree[2*u][j]&tree[2*u+1][j];
 }
 void rebuildFar(){
  if(far.empty()){B=-1;return;}bv=values[B];D=av^bv;delta=pc(D);if(delta>6)return;
  reserve=D&-D;variable.clear();constant.clear();constCode.clear();dBits.clear();which.fill(-2);
  for(U z=D;z;z&=z-1)dBits.push_back(bit(z));
  for(int code=0;code<(1<<delta);code++){
   int k=__builtin_popcount((unsigned)code),slack=min(3-k,3-delta+k);if(slack<0)continue;U I=0;
   for(int j=0;j<delta;j++)if(code>>j&1)I|=1ULL<<dBits[j];
   if(slack){which[code]=variable.size();variable.push_back(I);}else{which[code]=-1;constant.push_back(I);constCode.push_back(code);}
  }
  assert(variable.size()<=6);
  P=1;while(P<(int)far.size())P*=2;
  array<U,7> neutral;neutral.fill(~0ULL);tree.assign(2*P,neutral);
  for(int i=0;i<(int)far.size();i++)tree[P+i]=maskFor(values[far[i]]);
  for(int u=P-1;u;u--)for(int j=0;j<7;j++)tree[u][j]=tree[2*u][j]&tree[2*u+1][j];
 }
 void rebuildAll(){
  av=values[A];adj.fill(0);degree.fill(0);singles=used=0;edges=0;far.clear();
  for(int s:active){fpos[s]=-1;U e=values[s]^av;if(pc(e)<=2)graph(e,true);else{fpos[s]=far.size();far.push_back(s);}}
  B=far.empty()?-1:far[pick(far.size())];rebuildFar();
 }
 void begin(){removedA=removedB=false;}
 void eraseClass(int s){
  if(s==A)removedA=true;if(s==B)removedB=true;U e=values[s]^av;
  if(pc(e)<=2)graph(e,false);
  else{int p=fpos[s],z=far.back();if(p!=(int)far.size()-1)point(p,maskFor(values[z]));array<U,7> neutral;neutral.fill(~0ULL);point(far.size()-1,neutral);far[p]=z;fpos[z]=p;far.pop_back();fpos[s]=-1;}
  int p=pos[s],z=active.back();active[p]=z;pos[z]=p;active.pop_back();pos[s]=-1;byValue.erase(values[s]);freeSlots.push_back(s);
 }
 void end(int inserted){
  if(removedA){A=active[pick(active.size())];rebuildAll();return;}
  if(inserted>=0&&pick(active.size())==0){A=inserted;rebuildAll();return;}
  bool newFar=false;
  if(inserted>=0){U e=values[inserted]^av;if(pc(e)<=2)graph(e,true);else{fpos[inserted]=far.size();far.push_back(inserted);newFar=true;}}
  if(far.empty()){B=-1;return;}
  if(removedB||B<0){B=far[pick(far.size())];rebuildFar();return;}
  if(newFar&&pick(far.size())==0){B=inserted;rebuildFar();return;}
  if(delta<=6&&((int)far.size()>P||(int)far.size()<P/4)){rebuildFar();return;}
  if(newFar)point(fpos[inserted],maskFor(values[inserted]));
 }
 int badNear(U x)const{
  U C=x^av;int k=pc(C);assert(k<=3);
  if(k==3&&(singles&~C)){U e=(singles&~C)&-(singles&~C);return byValue.at(av^e);}
  if(k<2)return -1;
  int covered=0;U z=C;while(z){int u=bit(z);z&=z-1;covered+=degree[u];covered-=pc(adj[u]&z);}
  if(covered==edges)return -1;
  for(U q=used&~C;q;q&=q-1){int u=bit(q);U v=adj[u]&~C;if(v)return byValue.at(av^(1ULL<<u)^(v&-v));}
  assert(false);return -1;
 }
 int badFar(U x)const{
  if(far.empty())return -1;
  assert(pc(x^av)<=3&&pc(x^bv)<=3&&delta<=6);
  U C=x^av,J=C&~D;int code=0;for(int i=0;i<delta;i++)if(C>>dBits[i]&1)code|=1<<i;
  int w=which[code];U flag;if(w>=0){assert(pc(J)<=1);flag=J?J:reserve;}else{assert(w==-1&&!J);w=6;flag=1ULL<<code;}
  if(tree[1][w]&flag)return -1;
  int u=1;while(u<P){u*=2;if(tree[u][w]&flag)u++;}int s=far[u-P];assert(pos[s]>=0&&pc(values[s]^x)>3);return s;
 }
 void whole(U x,bool force){
  if(active.size()==1){
   int s=active[0];U v=values[s];if(v==x||(!force&&pc(v^x)<=3))return;
   int r=dsu.find(roots[s]);sum=U(dsu.t[r].cnt)*x;byValue.erase(v);byValue[x]=s;values[s]=av=x;dsu.t[r].value=x;return;
  }
  auto it=byValue.find(x);int targetSlot=it==byValue.end()?-1:it->second;int target=targetSlot<0?-1:dsu.find(roots[targetSlot]);
  begin();bool changed=false;
  auto remove=[&](int s){
   U v=values[s];int r=dsu.find(roots[s]);sum+=U(dsu.t[r].cnt)*(x-v);eraseClass(s);changed=true;
   if(target<0){target=r;dsu.t[target].value=x;}else target=dsu.merge(target,r,x);
   if(targetSlot>=0)roots[targetSlot]=target;
  };
  if(force||pc(av^x)>3){
   for(int i=0;i<(int)active.size();){int s=active[i];if(values[s]!=x&&(force||pc(values[s]^x)>3))remove(s);else i++;}
  }else{
   while(true){int s=badNear(x);if(s<0)break;remove(s);}
   if(B>=0&&pc(bv^x)>3){
    for(int i=0;i<(int)far.size();){int s=far[i];if(pc(values[s]^x)>3)remove(s);else i++;}
   }else while(true){int s=badFar(x);if(s<0)break;remove(s);}
  }
  if(!changed)return;
  int inserted=-1;if(targetSlot<0)inserted=insertClass(x,target);end(inserted);
 }
 void partial(int l,int r,U x,bool force){
  auto it=byValue.find(x);int targetSlot=it==byValue.end()?-1:it->second;int target=targetSlot<0?-1:dsu.find(roots[targetSlot]);
  begin();bool changed=false;
  for(int i=l;i<=r;i++){
   int old=dsu.find(ids[i]);U v=dsu.t[old].value;if(v==x||(!force&&pc(v^x)<=3))continue;
   if(target<0)target=dsu.make(x,0);
   dsu.t[old].cnt--;dsu.t[target].cnt++;ids[i]=target;sum+=x-v;changed=true;
   if(!dsu.t[old].cnt)eraseClass(byValue.at(v));
  }
  if(!changed)return;
  int inserted=-1;if(targetSlot<0)inserted=insertClass(x,target);end(inserted);
 }
 U query(int l,int r){U ans=0;for(int i=l;i<=r;i++)ans+=dsu.t[dsu.find(ids[i])].value;return ans;}
};
int main(){
 ios::sync_with_stdio(false);cin.tie(nullptr);int n,m,d;if(!(cin>>n>>m>>d))return 0;assert(d==3);
 vector<U> a(n);for(U& v:a)cin>>v;constexpr int BS=CP_BLOCK_SIZE;vector<Block> blocks;blocks.reserve((n+BS-1)/BS);
 for(int l=0;l<n;l+=BS)blocks.emplace_back(vector<U>(a.begin()+l,a.begin()+min(n,l+BS)));
 while(m--){int op,l,r;U x=0;cin>>op>>l>>r;--l;--r;if(op!=2)cin>>x;
  int lb=l/BS,rb=r/BS;U ans=0;
  for(int b=lb;b<=rb;b++){
   int L=max(l-b*BS,0),R=min(r-b*BS,blocks[b].size-1);bool full=L==0&&R==blocks[b].size-1;
   if(op==2)ans+=full?blocks[b].sum:blocks[b].query(L,R);
   else if(full)blocks[b].whole(x,op==3);else blocks[b].partial(L,R,x,op==3);
  }
  if(op==2)cout<<ans<<'\n';
 }
}
