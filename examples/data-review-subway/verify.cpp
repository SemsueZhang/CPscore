#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <queue>
#include <set>
#include <vector>
using namespace std;
using ll=long long;
const ll INF=4000000000000000000LL;
void need(bool x,const char*s){if(!x){fprintf(stderr,"INVALID %s\n",s);exit(2);}}
int main(int argc,char**argv){
    need(argc==3,"arguments");FILE*f=fopen(argv[1],"r"),*a=fopen(argv[2],"r");need(f&&a,"files");
    int c,n,m,d,q;need(fscanf(f,"%d%d%d%d%d",&c,&n,&m,&d,&q)==5,"header");
    need(0<=c&&c<=25&&1<=n&&n<=500&&1<=m&&m<=500000&&1<=d&&d<=20&&1<=q&&q<=100000,"header-range");
    vector<ll>w(m);for(auto&x:w){need(fscanf(f,"%lld",&x)==1,"w");need(1<=x&&x<=1000000000,"w-range");}
    vector<vector<pair<int,ll>>>at(m);int total=0,maxk=0;ll mint=INF,maxt=0;
    for(int i=0,k;i<n;i++){
        need(fscanf(f,"%d",&k)==1,"k");need(1<=k&&k<=m,"k-range");total+=k;maxk=max(maxk,k);set<int>seen;
        for(int j=0;j<k;j++){
            int v;ll t;need(fscanf(f,"%d%lld",&v,&t)==2,"a,t");need(1<=v&&v<=m&&1<=t&&t<=1000000000,"a,t-range");--v;
            need(seen.insert(v).second,"duplicate-station");at[v].push_back({i,t});mint=min(mint,t);maxt=max(maxt,t);
        }
    }
    need(m<=total&&total<=500000,"total");
    int ncap=500,scap=500000,qcap=100000;
    if(c>=1&&c<=3){ncap=3;scap=10;qcap=10;}
    if(c>=4&&c<=6){ncap=50;scap=300;qcap=200;}
    if(c>=7&&c<=8){ncap=200;scap=400;qcap=200;}
    if(c>=9&&c<=11)scap=1000;
    if(c>=12&&c<=15){scap=20000;qcap=2000;}
    if(c==20||c==21)ncap=2;
    need(n<=ncap&&total<=scap&&q<=qcap,"point-range");
    if(c>=7&&c<=11)need(maxk<=2,"property-A");
    if(c>=12&&c<=19)need(mint==maxt,"property-B");
    if(c==22||c==23)need(d<=2,"point-d");
    vector<vector<pair<int,ll>>>g(n);int maxdeg=0;
    vector<vector<int>>shared(n,vector<int>(n));int maxshared=0;
    for(auto &ls:at){
        need(!ls.empty()&&(int)ls.size()<=d,"coverage-degree");maxdeg=max(maxdeg,(int)ls.size());
        for(int i=0;i<(int)ls.size();i++)for(int j=i+1;j<(int)ls.size();j++)maxshared=max(maxshared,++shared[ls[i].first][ls[j].first]);
        if(ls.size()>1){int hall=g.size();g.emplace_back();for(auto p:ls){int i=p.first;ll t=p.second;g[i].push_back({hall,t});g[hall].push_back({i,t});}}
    }
    vector<vector<ll>>dist(n,vector<ll>(n));
    for(int s=0;s<n;s++){
        vector<ll>dv(g.size(),INF);dv[s]=0;
        priority_queue<pair<ll,int>,vector<pair<ll,int>>,greater<pair<ll,int>>>pq;pq.push({0,s});
        while(!pq.empty()){
            ll du=pq.top().first;int u=pq.top().second;pq.pop();if(du!=dv[u])continue;
            for(auto p:g[u]){int v=p.first;ll t=p.second;if(du+t<dv[v]){dv[v]=du+t;pq.push({dv[v],v});}}
        }
        for(int j=0;j<n;j++){need(dv[j]<INF,"connectivity");dist[s][j]=dv[j];}
    }
    int mismatches=0;ll maxans=0;
    for(int z=0;z<q;z++){
        int x,y;ll expected;need(fscanf(f,"%d%d",&x,&y)==2,"query");need(1<=x&&x<=m&&1<=y&&y<=m&&x!=y,"query-range");--x;--y;
        ll ans=INF;for(auto px:at[x])for(auto py:at[y])ans=min(ans,px.second+dist[px.first][py.first]+py.second+w[x]+w[y]);
        need(fscanf(a,"%lld",&expected)==1,"answer-count");mismatches+=ans!=expected;maxans=max(maxans,ans);
    }
    char tail;need(fscanf(f," %c",&tail)==EOF&&fscanf(a," %c",&tail)==EOF,"trailing");
    printf("point=%d valid=1 q=%d mismatch=%d n=%d sumK=%d maxDegree=%d maxShared=%d maxAnswer=%lld\n",c,q,mismatches,n,total,maxdeg,maxshared,maxans);
    return mismatches?1:0;
}
