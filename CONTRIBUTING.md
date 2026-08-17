# Contributing to MyAI

感谢你关注 MyAI。项目当前以 Windows 本地个人智能体 Demo 和毕业设计工程证据为主要范围。提交变更前，请先阅读 [项目总体审计](docs/PROJECT_FINAL_AUDIT.md)、[开发流程](docs/DEVELOPMENT_WORKFLOW.md) 和 [安全策略](SECURITY.md)。

## 开始之前

- 先用 Issue 或 Draft Pull Request 说明问题、目标、边界和验收方式；
- 优先提交可验证的小变更，不在一个 PR 中混合无关重构、格式化和功能；
- 尊重 Java/Python 权威边界：Java 管理身份、归属、会话和消息；Python 管理智能体运行；
- 新功能应给出最小可用范围、失败模式和已知限制，不以生产级措辞包装实验性能力。

仓库当前尚未附 LICENSE。提交外部贡献前，请先与维护者在 Issue 中确认许可安排；提交者必须拥有所提交内容的权利。

## 开发环境

支持的基线：

- Windows 10/11 x64；
- Python 3.12 x64；
- Java 17+；
- PowerShell 5.1 或 PowerShell 7；
- Node.js 22 用于完整前端静态门禁。

安装 Python 依赖：

~~~powershell
py -3.12 -m venv myai-python-agent\.venv
.\myai-python-agent\.venv\Scripts\python.exe -m pip install --requirement myai-python-agent\requirements.txt
~~~

检查并启动 Stub 本地模式：

~~~powershell
.\start-myai.cmd doctor -LocalMode
.\start-myai.cmd -LocalMode
~~~

Stub 模式用于确定性测试和功能链路验证。若修改真实模型集成，请同时记录 provider、模型、embedding、超时、回退策略、硬件和可复现命令。

## 必须通过的检查

从仓库根目录运行：

~~~powershell
.\scripts\ci-quality-gates.ps1
~~~

Python：

~~~powershell
cd myai-python-agent
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -p "test_*.py"
~~~

Java：

~~~powershell
cd myai-java-service
.\mvnw.cmd --batch-mode --no-transfer-progress verify
~~~

提交前再运行：

~~~powershell
git diff --check
~~~

若变更便携包逻辑，还需执行 [便携版构建与验证](docs/PORTABLE_APP.md) 中的 build、verify 和 controls 流程。

## 测试与文档原则

- 修复缺陷时先添加能复现问题的测试，再实现最小修复；
- 测试必须使用临时目录、合成数据和 Stub/隔离 provider，不能读取开发者真实数据库或 .env；
- 修改 API、配置、启动流程、数据边界或已知限制时同步更新文档；
- 实验数据应区分 pilot 与 formal，记录数据摘要、模型摘要、硬件、种子和统计单位；
- 不把技术重复次数当作独立样本数，不隐去负面结果。

## 安全与隐私

禁止提交：

- .env、config/app.env 或 scripts/start-myai.env；
- 密码、token、API key、cookie、私钥或连接字符串；
- 本地 SQLite、Chroma、知识库上传、日志、诊断包或模型权重；
- 真实用户对话、记忆、文件内容、账户名或机器绝对路径。

示例必须使用显然合成的值。即使某个密钥已经失效，也应先轮换并从待发布历史中清除，再进行推送。

## Pull Request 检查表

- [ ] PR 描述了问题、方案、边界和用户可见影响；
- [ ] 变更范围单一，没有夹带个人运行产物；
- [ ] Python/Java 相关测试已更新并本地通过；
- [ ] 静态质量门禁与 git diff --check 通过；
- [ ] 配置、架构、发布或限制文档已同步；
- [ ] 没有新增密钥、个人数据或本机绝对路径；
- [ ] 对真实模型结论提供可复现证据，对未验证内容明确标注；
- [ ] 对兼容性或迁移风险给出回滚/恢复说明。

维护者会重点审查安全边界、数据归属、兼容性、测试隔离、失败语义和公开表述是否与证据一致。
