#include <algorithm>
#include <array>
#include <iostream>
#include <vector>
using namespace std;
struct Aggregate {
 int count=0,s0=0,s1=0,best=0,first=1000000000,second=1000000000;
 void add(array<int,2> f){
  count++;s0+=f[0];s1+=f[1];best+=min(f[0],f[1]);int d=f[0]-f[1];
  if(d<first){second=first;first=d;}else if(d<second)second=d;
 }
 Aggregate without(array<int,2> f)const{
  Aggregate z=*this;z.count--;z.s0-=f[0];z.s1-=f[1];z.best-=min(f[0],f[1]);
  if(f[0]-f[1]==first)z.first=second;
  return z;
 }
};
array<int,2> message(int a,const Aggregate& z){
 if(a==1)return {1+z.best,1+z.best};
 if(a>=2)return {2+z.best,min(1+z.s1,2+z.best)};
 int f0=min(z.s0,2+z.best),f1=z.s0;
 if(z.count)f1=min(f1,2+z.best+max(0,z.first));
 return {f0,f1};
}
int main(){
 ios::sync_with_stdio(false);cin.tie(nullptr);
 int T;cin>>T;while(T--){
  int n;cin>>n;vector<vector<int>> g(n);for(int i=1,u,v;i<n;i++){cin>>u>>v;--u;--v;g[u].push_back(v);g[v].push_back(u);}
  vector<int> a(n);for(int& x:a){long long v;cin>>v;x=v==0?0:(v==1?1:2);}
  vector<int> parent(n,-1),order{0};parent[0]=0;
  for(int i=0;i<n;i++){int u=order[i];for(int v:g[u])if(parent[v]<0){parent[v]=u;order.push_back(v);}}
  vector<array<int,2>> down(n),up(n);
  for(int i=n-1;i>=0;i--){int u=order[i];Aggregate z;for(int v:g[u])if(parent[v]==u)z.add(down[v]);down[u]=message(a[u],z);}
  int ans=3*n;
  for(int u:order){
   Aggregate z;if(u)z.add(up[u]);for(int v:g[u])if(parent[v]==u)z.add(down[v]);
   ans=min(ans,n+message(a[u],z)[1]);
   for(int v:g[u])if(parent[v]==u)up[v]=message(a[u],z.without(down[v]));
  }
  cout<<ans<<'\n';
 }
}
