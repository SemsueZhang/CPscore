# 待审核程序

目前提供的题面摘录为：输入n和n个整数，输出其总和。完整题面、n的范围、整数范围、时空限制和目标运行环境暂未提供。

程序如下：

```cpp
#include <iostream>
int main() {
    int n;
    if (!(std::cin >> n)) return 0;
    long long sum = 0, x;
    for (int i = 0; i < n; ++i) {
        std::cin >> x;
        sum += x;
    }
    std::cout << sum << '\n';
}
```
