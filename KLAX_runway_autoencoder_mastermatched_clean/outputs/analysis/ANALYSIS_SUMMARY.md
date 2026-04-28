# KLAX Runway-Conditioned Anomaly Analysis

## 1. Runway-level score distribution and anomaly rate

runway  n_trajectories  mean_score  median_score  p95_score  p99_score  top5_count  top5_rate  top1_count  top1_rate
   25L            2432    0.002734      0.000529   0.012170   0.022327         122   0.050164          25   0.010280
   24R            2139    0.005661      0.003995   0.018609   0.029718         107   0.050023          22   0.010285
   06L             242    0.011389      0.007382   0.036285   0.052156          13   0.053719           3   0.012397
   24L             125    0.010266      0.008117   0.026468   0.032789           7   0.056000           2   0.016000
   06R              49    0.009088      0.002349   0.052584   0.063355           3   0.061224           1   0.020408
   25R              44    0.036193      0.016555   0.107906   0.141334           3   0.068182           1   0.022727
   07L              23    0.048414      0.032909   0.108200   0.108508           2   0.086957           1   0.043478
   07R              23    0.019301      0.014045   0.043129   0.063718           2   0.086957           1   0.043478

Interpretation: Runway 07L has the highest mean anomaly score (0.0484), while runway 07L has the highest top-5% anomaly rate (8.70%). Smaller runway groups such as 25R and 07L show higher average anomaly levels, which suggests either more irregular approach structure or greater sensitivity to limited sample size.

## 2. Daily anomaly count and intensity

sample_day  n_trajectories  mean_score  median_score  p95_score  top5_count  top1_count  top5_rate  top1_rate
2017-06-05            1036    0.004793      0.002133   0.017489          52          11   0.050193   0.010618
2017-06-12            1050    0.006288      0.004097   0.020890          67          12   0.063810   0.011429
2017-06-19            1056    0.005030      0.001937   0.018502          52           7   0.049242   0.006629
2017-06-26            1020    0.004675      0.001698   0.017842          37          11   0.036275   0.010784
2017-07-03             915    0.005184      0.001841   0.020769          51          15   0.055738   0.016393

Interpretation: The largest anomaly count occurs on 2017-06-12 with 67 top-5% anomalies, while the strongest anomaly intensity appears on 2017-06-12 with a 95th-percentile score of 0.0209. Count and intensity should be read together, since some days may have fewer anomalies but more severe individual outliers.

## 3. Top-6 anomaly interpretation

1. `Runway 25R` | `KLAX_20170605_29845d_NOCALL_1496703890` | score `0.1582`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; the segment is shorter than the runway-group median, so partial observation may also contribute to the score ; the track approaches from a substantially different heading before merging onto final.
2. `Runway 25R` | `KLAX_20170619_aa56db_UAL706_1497845670` | score `0.1190`: its flown path is noticeably less direct than the typical trajectory in the same runway group ; the trajectory is longer than the runway-specific median, consistent with a widened or delayed turn-in ; it appears to align with runway heading later than typical traffic in the same group ; the track approaches from a substantially different heading before merging onto final.
3. `Runway 07L` | `KLAX_20170619_a46f82_NOCALL_1497887840` | score `0.1085`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final.
4. `Runway 07L` | `KLAX_20170605_a2fee9_NOCALL_1496625130` | score `0.1084`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final ; the track approaches from a substantially different heading before merging onto final.
5. `Runway 25R` | `KLAX_20170605_a7ad84_DAL1212_1496661810` | score `0.1084`: its flown path is noticeably less direct than the typical trajectory in the same runway group ; the trajectory is longer than the runway-specific median, consistent with a widened or delayed turn-in ; it appears to align with runway heading later than typical traffic in the same group ; the track approaches from a substantially different heading before merging onto final.
6. `Runway 07L` | `KLAX_20170626_ad50a9_NOCALL_1498448120` | score `0.1063`: classified as VECTORED_FINAL, suggesting controller vectoring or a non-standard join to final.