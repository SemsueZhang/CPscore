#include <algorithm>
#include <array>
#include <cassert>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
using namespace std;
constexpr int MOD=998244353;
int addm(int a,int b){a+=b;return a>=MOD?a-MOD:a;}
int subm(int a,int b){a-=b;return a<0?a+MOD:a;}
int mul(int a,int b){return int(1LL*a*b%MOD);}
int power(int a,int b){int r=1;for(;b;b>>=1,a=mul(a,a))if(b&1)r=mul(r,a);return r;}
void ntt(vector<int>& a,bool inv){
 int n=a.size();
 for(int i=1,j=0;i<n;i++){int bit=n>>1;for(;j&bit;bit>>=1)j^=bit;j^=bit;if(i<j)swap(a[i],a[j]);}
 for(int len=2;len<=n;len<<=1){
  int wlen=power(3,(MOD-1)/len);if(inv)wlen=power(wlen,MOD-2);
  for(int i=0;i<n;i+=len){int w=1;for(int j=0;j<len/2;j++){
   int u=a[i+j],v=mul(a[i+j+len/2],w);a[i+j]=addm(u,v);a[i+j+len/2]=subm(u,v);w=mul(w,wlen);
  }}
 }
 if(inv){int z=power(n,MOD-2);for(int& x:a)x=mul(x,z);}
}
struct Kernels{vector<int> f,g,j;};
vector<int> fac;
map<int,Kernels> cache;
Kernels& kernels(int n){
 auto it=cache.find(n);if(it!=cache.end())return it->second;
 Kernels k;k.f.resize(n);k.g.resize(n);k.j.resize(n);
 for(int t=0;t<n;t++){k.f[t]=fac[t];k.g[t]=mul(t,fac[t]);k.j[t]=mul(mul(t,(t+MOD-1)%MOD),fac[t]);}
 ntt(k.f,false);ntt(k.g,false);ntt(k.j,false);
 return cache.emplace(n,std::move(k)).first->second;
}
array<int,3> transfer(const array<int,3>& u,int t){
 int f=fac[t],g=mul(t,f),h=mul(t+1,f),j=mul(mul(t,(t+MOD-1)%MOD),f);
 return {mul(u[0],h),addm(mul(u[0],addm(g,g)),mul(u[1],f)),addm(addm(mul(u[0],j),mul(u[1],g)),mul(u[2],h))};
}
int finish(const array<int,3>& u,int t){
 assert(t>=1);return mul(fac[t],addm(mul(u[0],t-1),addm(u[1],u[2])));
}
int solve(const string& a,const string& b){
 int n=a.size();if(a.front()=='0'||a.back()=='0'||b.front()=='0'||b.back()=='0')return 0;
 vector<int> forced;for(int i=1;i<n;i++)if(a[i-1]=='1'||b[i]=='1')forced.push_back(i);forced.push_back(n);
 array<int,3> init{};int prev=0;
 for(int end:forced){
  int len=end-prev,L=len-1;
  vector<array<int,3>> f(L+1),c(L+1);
  auto base=[&](int t){if(prev==0)return array<int,3>{fac[t],addm(fac[t],fac[t]),mul(t-1,fac[t])};return transfer(init,t);};
  for(int i=1;i<=L;i++)f[i]=base(i);
  auto filter=[&](int i){
   int at=prev+i;bool bad[3]={a[at-1]=='0',a[at-1]=='0'||b[at]=='0',b[at]=='0'};
   for(int s=0;s<3;s++)if(bad[s])c[i][s]=f[i][s]?MOD-f[i][s]:0;
  };
  function<void(int,int)> cdq=[&](int l,int r){
   if(l==r){filter(l);return;}
   int m=(l+r)/2;cdq(l,m);
   if(r-l+1<=48){
    for(int i=m+1;i<=r;i++)for(int j=l;j<=m;j++){
     auto v=transfer(c[j],i-j);for(int s=0;s<3;s++)f[i][s]=addm(f[i][s],v[s]);
    }
   }else{
    bool active[3]={};for(int i=l;i<=m;i++)for(int s=0;s<3;s++)active[s]|=c[i][s]!=0;
    if(active[0]||active[1]||active[2]){
     int N=1;while(N<r-l+1)N<<=1;auto& k=kernels(N);
     array<vector<int>,3> A,V;for(auto& v:A)v.assign(N,0);for(auto& v:V)v.assign(N,0);
     for(int s=0;s<3;s++)if(active[s]){for(int i=l;i<=m;i++)A[s][i-l]=c[i][s];ntt(A[s],false);}
     for(int z=0;z<N;z++){
      int h=addm(k.f[z],k.g[z]);
      V[0][z]=mul(A[0][z],h);
      V[1][z]=addm(mul(A[0][z],addm(k.g[z],k.g[z])),mul(A[1][z],k.f[z]));
      V[2][z]=addm(addm(mul(A[0][z],k.j[z]),mul(A[1][z],k.g[z])),mul(A[2][z],h));
     }
     for(int s=0;s<3;s++)if(active[0]||(s>=1&&active[1])||(s==2&&active[2])){
      ntt(V[s],true);for(int i=m+1;i<=r;i++)f[i][s]=addm(f[i][s],V[s][i-l]);
     }
    }
   }
   cdq(m+1,r);
  };
  if(L)cdq(1,L);
  if(end==n){
   int ans=prev==0?fac[n]:finish(init,len);
   for(int i=1;i<=L;i++)ans=addm(ans,finish(c[i],len-i));return ans;
  }
  auto out=base(len);for(int i=1;i<=L;i++){
   auto v=transfer(c[i],len-i);for(int s=0;s<3;s++)out[s]=addm(out[s],v[s]);
  }
  int X[3]={1,1,0},Y[3]={0,1,1};
  for(int s=0;s<3;s++)if((a[end-1]!='?'&&a[end-1]-'0'!=X[s])||(b[end]!='?'&&b[end]-'0'!=Y[s]))out[s]=0;
  init=out;prev=end;
 }
 return 0;
}
int main(){
 ios::sync_with_stdio(false);cin.tie(nullptr);
 int T;cin>>T;vector<pair<string,string>> all;int mx=2;
 while(T--){int n;string a,b;cin>>n>>a>>b;all.emplace_back(a,b);mx=max(mx,n);}
 int N=1;while(N<mx)N<<=1;fac.resize(N+1);fac[0]=1;for(int i=1;i<=N;i++)fac[i]=mul(fac[i-1],i);
 for(auto& [a,b]:all)cout<<solve(a,b)<<'\n';
}
