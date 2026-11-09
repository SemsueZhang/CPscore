#include <iostream>
int main() {
    int n;
    if (!(std::cin >> n)) return 1;
    long long answer = 1, value;
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> value)) return 1;
        answer += value;
    }
    std::cout << answer << '\n';
}
