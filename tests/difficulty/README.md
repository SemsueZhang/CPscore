# Difficulty 基础测试

所有材料与预测均为合成接口输入，不调用模型，不是准确率成绩。

```sh
python3 -m unittest discover -s tests/difficulty -p 'test_*.py' -v
LUOGUBENCH_ROOT=/absolute/path/LuoguBench python3 -m unittest discover -s tests/difficulty -p 'test_*.py' -v
```

无外部工程时运行 27 项本地测试并跳过 4 项集成检查。指定已有 LuoguBench 路径时，31 项全部运行。检查原生范围与未知、输出字段和档名、输入白名单、题目/解法身份及冻结哈希、家族隔离、专家确认与手工发版、独立安装、适配器禁止工具、并发单题的身份绑定、历史文件指纹，以及现有指标实现的接口。

CI 运行本地测试，不下载外部工程，不运行昂贵 Benchmark。原版平台工具另用本地既有 `.github/scripts/test-difficulty.py` 验证。
