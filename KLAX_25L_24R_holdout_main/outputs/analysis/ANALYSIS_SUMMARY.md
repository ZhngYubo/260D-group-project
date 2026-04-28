# KLAX Runway-Conditioned Anomaly Analysis

## 1. Runway-level score distribution and anomaly rate

runway  n_trajectories  mean_score  median_score  p95_score  p99_score  top5_count  top5_rate  top1_count  top1_rate
   25L             487    0.004314      0.000907   0.017731   0.024603          27   0.055441           3   0.006160
   24R             428    0.009928      0.003945   0.020676   0.039513          33   0.077103          11   0.025701

Interpretation: Runway 24R has the highest mean anomaly score (0.0099), while runway 24R has the highest top-5% anomaly rate (7.71%). Smaller runway groups such as 25R and 07L show higher average anomaly levels, which suggests either more irregular approach structure or greater sensitivity to limited sample size.

## 2. Daily anomaly count and intensity

sample_day  n_trajectories  mean_score  median_score  p95_score  top5_count  top1_count  top5_rate  top1_rate
2017-06-05             204    0.014001      0.002871   0.018042          14           3   0.068627   0.014706
2017-06-12             178    0.006025      0.004360   0.018647          10           1   0.056180   0.005618
2017-06-19             187    0.004274      0.001603   0.017349          10           2   0.053476   0.010695
2017-06-26             183    0.004478      0.001163   0.020692          14           5   0.076503   0.027322
2017-07-03             163    0.004925      0.001757   0.021516          12           3   0.073620   0.018405

Interpretation: The largest anomaly count occurs on 2017-06-05 with 14 top-5% anomalies, while the strongest anomaly intensity appears on 2017-07-03 with a 95th-percentile score of 0.0215. Count and intensity should be read together, since some days may have fewer anomalies but more severe individual outliers.

## 3. Top-6 anomaly interpretation

1. `Runway 24R` | `KLAX_20170605_a6c6c8_ASA962_1496643850` | score `1.5721`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; the trajectory is longer than the runway-specific median, consistent with a widened or delayed turn-in ; it appears to align with runway heading later than typical traffic in the same group ; the track approaches from a substantially different heading before merging onto final.
2. `Runway 24R` | `KLAX_20170605_acae9a_NOCALL_1496675180` | score `0.1778`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; its flown path is noticeably less direct than the typical trajectory in the same runway group ; the segment is shorter than the runway-group median, so partial observation may also contribute to the score.
3. `Runway 25L` | `KLAX_20170605_2982fb_NOCALL_1496692750` | score `0.1578`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; its flown path is noticeably less direct than the typical trajectory in the same runway group ; it appears to align with runway heading later than typical traffic in the same group ; the segment is shorter than the runway-group median, so partial observation may also contribute to the score ; the track approaches from a substantially different heading before merging onto final.
4. `Runway 24R` | `KLAX_20170612_2986c0_NOCALL_1497280400` | score `0.0458`: its flown path is noticeably less direct than the typical trajectory in the same runway group ; it appears to align with runway heading later than typical traffic in the same group ; the segment is shorter than the runway-group median, so partial observation may also contribute to the score ; the track approaches from a substantially different heading before merging onto final.
5. `Runway 24R` | `KLAX_20170626_a67439_N515CE_1498489250` | score `0.0441`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; the track approaches from a substantially different heading before merging onto final.
6. `Runway 24R` | `KLAX_20170626_acd9d0_NOCALL_1498485020` | score `0.0398`: its flown path is noticeably less direct than the typical trajectory in the same runway group ; it appears to align with runway heading later than typical traffic in the same group ; the track approaches from a substantially different heading before merging onto final.