#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <cstring>
#include <queue>
#include <vector>
using namespace std;
using ll=long long;
const ll INF=4000000000000000000LL;
int main(int argc,char**argv){
    // Each mode changes one mechanism in the same correct line-graph solver.
    const char* names[] = {"correct", "parallel_overwrite", "adjacent_only",
        "two_endpoints", "nearest_platform", "early_visited", "floyd_ikj",
        "unsorted_lookup", "infinity_1e12", "unused", "int32_distances"};
    int mode=0;
    if(argc>1){
        for(mode=0;mode<=10;mode++)if(strcmp(argv[1],names[mode])==0)break;
        if(mode>10||mode==9){fprintf(stderr,"unknown candidate\n");return 2;}
    }
    int c,n,m,d,q;
    if(scanf("%d%d%d%d%d",&c,&n,&m,&d,&q)!=5)return 2;
    vector<ll>w(m);
    for(auto &v:w)scanf("%lld",&v);
    vector<vector<pair<int,ll>>> at(m),line(n);
    for(int i=0,k;i<n;i++){
        scanf("%d",&k);
        while(k--){int v;ll t;scanf("%d%lld",&v,&t);--v;at[v].push_back({i,t});line[i].push_back({v,t});}
    }
    vector<vector<ll>> dist(n,vector<ll>(n,INF));
    for(int i=0;i<n;i++)dist[i][i]=0;
    for(auto &ls:at)for(int i=0;i<(int)ls.size();i++)for(int j=i+1;j<(int)ls.size();j++){
        if(mode==2 && j!=i+1)continue;
        int u=ls[i].first,v=ls[j].first;ll a=ls[i].second,b=ls[j].second;
        if(mode==1)dist[u][v]=dist[v][u]=a+b;
        else dist[u][v]=dist[v][u]=min(dist[u][v],a+b);
    }
    if(mode==5){
        auto edge=dist;
        for(int s=0;s<n;s++){
            fill(dist[s].begin(),dist[s].end(),INF);
            vector<bool>seen(n);seen[s]=true;dist[s][s]=0;
            priority_queue<pair<ll,int>,vector<pair<ll,int>>,greater<pair<ll,int>>>pq;pq.push({0,s});
            while(!pq.empty()){
                ll dv=pq.top().first;int v=pq.top().second;pq.pop();
                for(int u=0;u<n;u++)if(!seen[u]&&edge[v][u]!=INF){
                    seen[u]=true;dist[s][u]=dv+edge[v][u];pq.push({dist[s][u],u});
                }
            }
        }
    }else if(mode==6){
        for(int i=0;i<n;i++)for(int k=0;k<n;k++)for(int j=0;j<n;j++)dist[i][j]=min(dist[i][j],dist[i][k]+dist[k][j]);
    }else if(mode==10){
        // The unsigned addition exposes 32-bit wraparound without signed UB.
        vector<vector<int>>ds(n,vector<int>(n,2000000000));
        for(int i=0;i<n;i++)for(int j=0;j<n;j++)if(dist[i][j]!=INF)ds[i][j]=(int)dist[i][j];
        for(int k=0;k<n;k++)for(int i=0;i<n;i++)for(int j=0;j<n;j++)
            if(ds[i][k]!=2000000000 && ds[k][j]!=2000000000)ds[i][j]=min(ds[i][j],(int)((unsigned)ds[i][k]+(unsigned)ds[k][j]));
        for(int i=0;i<n;i++)for(int j=0;j<n;j++)dist[i][j]=ds[i][j];
    }else{
        for(int k=0;k<n;k++)for(int i=0;i<n;i++)for(int j=0;j<n;j++)dist[i][j]=min(dist[i][j],dist[i][k]+dist[k][j]);
    }
    auto lookup=[&](int id,int v){
        auto it=lower_bound(line[id].begin(),line[id].end(),make_pair(v,0LL));
        return it==line[id].end()||it->first!=v?INF:it->second;
    };
    while(q--){
        int x,y;scanf("%d%d",&x,&y);--x;--y;
        auto ax=at[x],ay=at[y];
        if(mode==3){if(ax.size()>2)ax.resize(2);if(ay.size()>2)ay.resize(2);}
        if(mode==4){auto cmp=[](auto a,auto b){return a.second<b.second;};sort(ax.begin(),ax.end(),cmp);sort(ay.begin(),ay.end(),cmp);ax.resize(1);ay.resize(1);}
        ll ans=mode==8?1000000000000LL:INF;
        for(auto px:ax)for(auto py:ay){
            int i=px.first,j=py.first;ll a=px.second,b=py.second;
            if(mode==7){a=lookup(i,x);b=lookup(j,y);if(a==INF||b==INF)continue;}
            ans=min(ans,dist[i][j]+a+b+w[x]+w[y]);
        }
        printf("%lld\n",ans);
    }
}
