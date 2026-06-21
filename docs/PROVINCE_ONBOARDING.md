# 新省份接入清单

这份清单用于把新的省份数据接入网站，目标是统一进入 `awards_master`，并在前端省份下拉、基础分析接口和页面展示中可用。

## 1. 原始数据准备

- 准备该省原始 Excel。
- 确认至少包含以下字段：
  - `成果名称`
  - `完成人`
  - `完成单位`
  - `获奖等级`
- 如果原始表缺少以下扩展字段，先补列：
  - `第一完成单位层次`
  - `第一完成单位学科类型`
  - `第一完成单位地理位置`

## 2. 字段补齐规则

- `第一完成单位层次`
  - 统一使用：`985` / `211` / `其他`
- `第一完成单位学科类型`
  - 当前统一使用：`综合类` / `理工类` / `师范类` / `医药类` / `财经类` / `农林类` / `其他类`
- `第一完成单位地理位置`
  - 非直辖市时按地市补齐。
  - 直辖市可暂时留空。

要求：
- 只填能稳定确认的信息。
- 搜不到或口径不稳的，先留空或由人工确认，不要猜。

## 3. Excel 补齐

- 用省份专用补齐脚本更新原始 Excel。
- 上海当前脚本在：
  - `data-pipeline/enrichers/fill_shanghai_metadata.py`
- 补齐后检查：
  - 是否仍有空的 `成果名称`
  - 是否仍有空的 `完成单位`
  - 是否存在未处理完的学校层次/学科类型

## 4. 导入统一主表

- 主表：`awards_master`
- 导入脚本：
  - `data-pipeline/importers/import_awards_master.py`

导入前确认：
- 省份名标准统一，例如 `浙江省`、`上海市`
- 年份明确
- Excel 已保存最新补齐结果

常用方式：

```powershell
python .\data-pipeline\importers\import_awards_master.py --skip-zhejiang --shanghai-year 2025
```

如果接入新省份，建议后续把导入脚本扩成可配置的省份参数，而不是继续写死到上海。

## 5. 后端接口检查

接入后至少验证这些接口：

- `/api/meta/options`
- `/api/v2/dist?province=省份名&year=年份&qtype=org`
- `/api/v2/dist?province=省份名&year=年份&qtype=award_level`
- `/api/v2/dist?province=省份名&year=年份&qtype=discipline`
- `/api/v2/dist?province=省份名&year=年份&qtype=org_level`
- `/api/v2/dist?province=省份名&year=年份&qtype=collab`
- `/api/v2/dist?province=省份名&year=年份&qtype=completion_mode`

检查点：
- 返回码是 `200`
- 省份出现在 `/api/meta/options`
- 年份正确
- 图表总量和该省导入条数一致或符合统计逻辑

## 6. 前端页面验收

页面地址：

- [http://localhost:5173/](http://localhost:5173/)

验收内容：
- 省份下拉里能看到新省份
- 选择该省后，年份下拉正确
- 只展示该省实际支持的分析类型
- 图表正常渲染
- 下载文件名和标题包含正确省份名
- 切回浙江省后，原功能不回退

## 7. 当前架构边界

已统一到 `awards_master` 的是基础分析主链：

- `org`
- `award_level`
- `discipline`
- `org_level`
- `collab`
- `completion_mode`

尚未完全统一的高级能力：

- `theme_table`
- `wordcloud`

这两项需要额外数据或派生表，不能只靠主 Excel 自动获得。

## 8. 每次接入后的最小验收清单

- 原始条数与导入条数一致
- 无空 `成果名称`
- 无空 `完成单位`
- 新省份出现在 `/api/meta/options`
- 前端下拉可选
- 至少 6 类基础分析可查询
- 浙江省原有查询正常

## 9. 上海试点结论

上海这次已经验证通过的内容：

- Excel 补齐后可导入统一主表
- 前端可动态显示 `上海市`
- 后端基础分析可按 `province` 正常返回
- 浙江省功能未被破坏

后续新省份接入时，优先复用这套流程，不再走“单省单表”的老路径。
