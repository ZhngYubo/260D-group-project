# KLAX 25L / 24R Holdout 主分析版本

这个文件夹是当前最终主线版本。

后续如果继续做结果分析、写报告、更新图表，默认都基于这里的文件，不再默认引用其他旧目录。

## 当前方法逻辑

- 只保留 `KLAX` 中样本量充足的两条常用到达跑道：`25L` 和 `24R`
- 使用逐点轨迹数据，按 `trajectory_id` 和真实 `runway` 标签组织样本
- 每个跑道分别训练一个轨迹自编码器
- 对每个跑道先划分 `80% train + 20% holdout`
- 模型只在 `train` 上训练
- 异常阈值也由 `train` 分数分布定义
- 主分析使用未见过的 `holdout` 样本分数

这个版本比“训练集内直接打分”的旧版更适合作为主结果，因为它更接近真正的未见样本异常检测。

## 样本量

- `25L`: 2432 条轨迹
- `24R`: 2139 条轨迹
- 合计：4571 条轨迹

## 文件结构

### `data/`
- `opensky_lax_segments_with_runway_25L_24R_only.csv`
  当前主线训练与评估数据。

### `scripts/`
- `train_pointwise_runway_autoencoder.py`
  当前主线训练脚本。输出 holdout 分数、train 分数、模型统计和模型文件。
- `make_runway_pointwise_png_comparison.py`
  生成异常轨迹与典型轨迹对比图。
- `analyze_runway_anomalies.py`
  生成跑道级统计、按天统计和 Top-6 异常解释。

### `outputs/`
- `runway_pointwise_anomaly_scores.csv`
  holdout 样本的异常分数。当前主分析最核心的结果表。
- `runway_pointwise_train_scores.csv`
  训练集样本分数，用于和 holdout 结果做对照。
- `runway_pointwise_model_stats.csv`
  跑道级模型统计，包含 train 与 holdout 两套分数摘要。
- `runway_pointwise_top_anomalies.csv`
  holdout 高分异常轨迹列表。
- `training_run_metadata.json`
  当前训练配置与规模。

### `outputs/models/`
- `runway_25L_autoencoder.joblib`
- `runway_24R_autoencoder.joblib`
- `model_metadata.json`

### `outputs/visualizations/`
- `anomaly_vs_typical_top4_25L_24R_only_holdout.png`
  当前推荐放入报告的异常与典型轨迹对比图。

### `outputs/analysis/`
- `runway_anomaly_summary.csv`
- `daily_anomaly_summary.csv`
- `top6_anomaly_explanations.csv`
- `runway_score_distribution.png`
- `daily_anomaly_trends.png`
- `ANALYSIS_SUMMARY.md`

## 最值得优先看的文件

- `outputs/runway_pointwise_anomaly_scores.csv`
- `outputs/runway_pointwise_train_scores.csv`
- `outputs/runway_pointwise_model_stats.csv`
- `outputs/analysis/runway_anomaly_summary.csv`
- `outputs/analysis/daily_anomaly_summary.csv`
- `outputs/analysis/top6_anomaly_explanations.csv`
- `outputs/visualizations/anomaly_vs_typical_top4_25L_24R_only_holdout.png`

## 后续可进一步分析的思路

- 对高分异常轨迹的解释
- 区分 VECTORED_FINAL 和 ALIGNED_FINAL
- 轨迹几何特征分析
- 结合天气、时间分析运营情况？
