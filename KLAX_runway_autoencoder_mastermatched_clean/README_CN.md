# KLAX 跑道分组异常检测主线文件说明

这个文件夹是当前推荐保留和继续使用的主线版本。

方法逻辑：
- 只使用 `master` 文件里已经定义好的有效 `KLAX trajectory_id`
- 将这些 `trajectory_id` 匹配回逐点轨迹数据
- 使用 `master` 中已有的真实 `runway` 标签分组
- 按跑道分别训练轨迹自编码器
- 用重构误差作为异常分数

## 文件夹结构

### `data/`
- `opensky_lax_segments_with_runway.csv`
  当前主线训练数据。已经是 `KLAX` 的逐点轨迹，并且已经带有真实跑道标签。

### `scripts/`
- `merge_segments_and_runway_labels.py`
  用 `trajectory_id` 将原始逐点轨迹和 `master` 里的跑道标签合并。
- `train_pointwise_runway_autoencoder.py`
  当前主线训练脚本。现在会同时保存异常分数、统计表、每个跑道的模型文件和训练元数据。
- `make_runway_pointwise_png_comparison.py`
  生成“异常轨迹 vs 典型轨迹”的 PNG 可视化图。
- `analyze_runway_anomalies.py`
  生成跑道分布、按天统计和 Top-6 异常解释等分析结果。

### `outputs/`
- `runway_pointwise_anomaly_scores.csv`
  每条轨迹的异常分数，是后续分析最核心的结果表。
- `runway_pointwise_model_stats.csv`
  每个跑道模型的统计汇总。
- `runway_pointwise_top_anomalies.csv`
  分数最高的异常轨迹列表。
- `training_run_metadata.json`
  本次训练的运行参数和训练规模。

### `outputs/models/`
- `runway_06L_autoencoder.joblib` 等
  每个跑道一个模型文件，内部包含该跑道的 `MLPRegressor` 和 `MinMaxScaler`。
- `model_metadata.json`
  模型集合的总体信息，例如训练跑道、随机种子和最小样本数。

### `outputs/visualizations/`
- `anomaly_vs_typical_top4_runway_lax_mastermatched_mixedbg.png`
  当前主线结果图。背景包含全机场浅灰轨迹和同跑道深灰轨迹。

### `outputs/analysis/`
- `runway_anomaly_summary.csv`
  每个跑道的异常分数分布和异常率汇总。
- `daily_anomaly_summary.csv`
  按天统计的异常数量和异常强度。
- `top6_anomaly_explanations.csv`
  最高分 6 条异常的文字解释。
- `runway_score_distribution.png`
  跑道级异常分布与异常率图。
- `daily_anomaly_trends.png`
  按天异常数量和强度图。
- `ANALYSIS_SUMMARY.md`
  当前分析结果的文字摘要。

## 你之后主要看哪些文件

如果只是继续分析结果，优先看：
- `outputs/runway_pointwise_anomaly_scores.csv`
- `outputs/analysis/runway_anomaly_summary.csv`
- `outputs/analysis/daily_anomaly_summary.csv`
- `outputs/analysis/top6_anomaly_explanations.csv`
- `outputs/visualizations/anomaly_vs_typical_top4_runway_lax_mastermatched_mixedbg.png`

如果要继续复现或扩展模型，优先看：
- `scripts/train_pointwise_runway_autoencoder.py`
- `outputs/models/`
- `outputs/training_run_metadata.json`

# 可能的问题：

- 数据方面可能预处理阶段未筛选长度较短的轨迹，导致较短轨迹异常评分较高。
