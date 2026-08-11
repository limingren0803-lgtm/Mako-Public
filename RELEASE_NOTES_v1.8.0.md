# Mako v1.8.0 Release Notes

发布日期：2026-08-11

## 版本范围

v1.8.0 增加求职用户对企业来源、职位核验窗口和数据使用方式的单次请求控制。该版本重点改善职位数据的透明度和安全降级，不改变 CareerProfile、Memory 或六个 Career Skill 的业务规则。

## 用户选择

`/chat` 新增两个可选字段：

- `job_source_ids`：选择最多 5 个已登记的活动官方来源；
- `job_data_mode`：选择 `verified_only` 或 `official_links_if_missing`。

本地职位检索只使用用户选择的来源。未选择来源时保持原有跨来源检索行为。来源选择、数据模式和核验窗口只作用于当前请求，不写入 CareerProfile 或 Memory。

## 数据状态

公开来源目录和聊天响应会说明当前是否存在可检索的本地职位、可用操作、岗位数量和最近核验时间。超过用户核验窗口、已经失效或缺少核验时间的职位不会标记为可检索。

本地数据不足时，`official_links_if_missing` 可以返回已登记的企业官方招聘入口。该入口仅作为目录信息，`job_data_used` 保持 `false`，回答不会把入口解释为具体在招职位。

## 安全边界

聊天请求不会实时访问招聘网站，也不能创建刷新任务。刷新、导入、审核和持久化任务接口继续位于管理员边界内。用户可见来源信息不包含自动化策略、来源错误或管理员任务字段。

## 兼容性

- 现有 API 路径、CareerProfile Schema、Memory 和 Career Skill 行为没有变化；
- Redis key、ChromaDB collections、Docker volume 和挂载位置没有变化；
- 职位登记库没有新增表或字段；
- 新增请求字段均为可选字段，不提供时保持既有行为；
- 自动获取策略保持关闭，升级不会启动后台抓取。

## 验证

- 公开基线回归、Python 编译与依赖审计通过；
- Docker Compose 配置和生产镜像构建通过；
- 五个 Compose 服务保持健康，重启次数为 0；
- 应用、Nginx、ChromaDB 和 Prometheus 在线检查通过；
- 管理接口和未知来源拒绝边界通过；
- 公开来源响应未发现管理字段或凭据内容。
