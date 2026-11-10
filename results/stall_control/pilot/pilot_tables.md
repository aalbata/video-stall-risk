# Development pilot tables

## dev_cv

Baselines

```
              qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
variant                                                                                                                                                                  
robust                 2.9844          0.0254           10.2513   2.7358            3.7668               0.0049                0.0072                 0.1226          0.0
hm                    -4.5445          0.0726           11.9447  14.0755            4.4194               0.0313                0.0524                 0.4399          0.0
model_robust           3.0351          0.0272           10.6417   2.4151            4.2861               0.0049                0.0065                 0.1156          0.0
```

Online margin, signal stall_event, step 0.5, floor 0

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps  stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                            
0.002           3.0897          0.0239            9.8380  2.8113            3.9768               0.0050                0.0079                 0.1610       0.6225
0.005           2.8694          0.0253           10.0418  3.1698            4.1211               0.0060                0.0095                 0.1731       0.5745
0.010           2.5533          0.0300           10.6677  4.1132            4.3522               0.0077                0.0116                 0.2070       0.4493
0.020           2.2700          0.0339           11.1632  5.4528            4.3486               0.0096                0.0156                 0.2457       0.3427
0.040           1.0251          0.0398           11.4201  6.7170            4.6195               0.0131                0.0210                 0.3176       0.1979
```

Online margin, signal overestimate, step 0.5, floor 0

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps  stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                            
0.05            3.8168          0.0165            9.0574  1.4717            3.7416               0.0018                0.0024                 0.0565       0.9049
0.10            3.2599          0.0235           10.2370  2.2264            4.0944               0.0038                0.0048                 0.1015       0.6595
0.20            2.3848          0.0302           11.0799  3.4717            4.7076               0.0064                0.0092                 0.1807       0.4183
0.30            1.0584          0.0360           11.4875  4.7547            5.0114               0.0092                0.0141                 0.2384       0.2909
0.40            0.7195          0.0389           11.6056  5.9245            5.2132               0.0116                0.0178                 0.2867       0.2146
```

Fixed margin

```
              qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
fixed_margin                                                                                                                                                             
-0.25                -13.1231          0.1027           12.4871  27.0377            5.3458               0.0558                0.1028                 0.7188        -0.25
 0.00                 -4.4911          0.0616           11.9175  12.2264            5.0484               0.0258                0.0422                 0.4398         0.00
 0.10                 -2.0018          0.0519           11.6834   9.3396            4.8210               0.0186                0.0300                 0.3366         0.10
 0.20                 -1.1821          0.0435           11.4696   7.3962            4.6798               0.0147                0.0241                 0.2510         0.20
 0.30                  0.0079          0.0393           11.3070   6.0189            4.4891               0.0117                0.0188                 0.1931         0.30
 0.40                  1.3285          0.0331           10.9678   4.6226            4.1864               0.0087                0.0127                 0.1455         0.40
 0.50                  1.6655          0.0303           10.6159   3.6792            4.1912               0.0066                0.0093                 0.1072         0.50
 0.60                  2.0690          0.0269            9.9977   3.1132            3.9330               0.0053                0.0074                 0.0846         0.60
 0.80                  2.3652          0.0205            8.8367   2.2075            3.6747               0.0034                0.0045                 0.0521         0.80
 1.00                  2.2758          0.0174            7.6778   1.8491            3.5044               0.0027                0.0034                 0.0339         1.00
 1.25                  1.6132          0.0146            6.2537   1.2075            3.4707               0.0017                0.0020                 0.0230         1.25
 1.50                  0.8435          0.0128            4.8872   1.0943            3.4015               0.0014                0.0016                 0.0163         1.50
```

Online margin on the harmonic mean

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                             
0.002           2.2249          0.0305            9.7770   4.3396            3.5883               0.0081                0.0140                 0.1768       0.5662
0.005           1.6486          0.0358           10.2746   4.9623            3.6003               0.0102                0.0170                 0.2079       0.4840
0.010           1.1250          0.0406           10.6627   7.2453            3.8099               0.0138                0.0249                 0.2726       0.3642
0.020          -1.4319          0.0550           11.2793  11.3962            4.1739               0.0213                0.0414                 0.3795       0.1713
0.040          -5.3116          0.0774           11.8267  18.0189            4.5125               0.0366                0.0652                 0.5000      -0.0071
```

## dev_mob

Baselines

```
              qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
variant                                                                                                                                                                  
robust                 0.8993          0.0335           10.0993   3.2286            3.8133               0.0059                0.0082                 0.1245          0.0
hm                    -7.2623          0.0844           11.9311  15.4857            4.4953               0.0338                0.0548                 0.4376          0.0
model_robust           1.7826          0.0288            9.8872   2.8857            4.1983               0.0047                0.0057                 0.1054          0.0
```

Online margin, signal stall_event, step 0.5, floor 0

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps  stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                            
0.002           1.1297          0.0290            8.9907  3.4857            3.9246               0.0058                0.0084                 0.1125       0.6872
0.005           0.8415          0.0326            9.4156  3.6571            3.9466               0.0065                0.0094                 0.1274       0.6072
0.010           0.6405          0.0354            9.9970  4.3714            4.0530               0.0083                0.0124                 0.1433       0.5249
0.020          -0.0443          0.0432           10.8278  5.6000            4.2057               0.0107                0.0165                 0.1945       0.3528
0.040          -1.9039          0.0511           11.1945  7.6857            4.5272               0.0150                0.0230                 0.2615       0.2119
```

Online margin, signal overestimate, step 0.5, floor 0

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps  stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                            
0.05            1.7103          0.0243            8.5032  1.7143            3.6849               0.0027                0.0033                 0.0547       0.9141
0.10            1.2080          0.0307            9.8700  2.5143            4.1566               0.0040                0.0051                 0.0977       0.6236
0.20            1.3429          0.0336           10.7576  4.2571            4.6757               0.0071                0.0101                 0.1666       0.3941
0.30           -1.8935          0.0475           11.1400  5.1429            5.0152               0.0093                0.0136                 0.2131       0.2579
0.40           -1.0163          0.0473           11.4046  6.5429            5.0668               0.0120                0.0181                 0.2464       0.1860
```

Fixed margin

```
              qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
fixed_margin                                                                                                                                                             
-0.25                -13.1625          0.1041           12.3440  24.3714            5.3879               0.0510                0.0880                 0.6008        -0.25
 0.00                 -6.3524          0.0739           11.8103  14.2571            4.9517               0.0276                0.0468                 0.3717         0.00
 0.10                 -4.5040          0.0605           11.4722  10.5143            4.6236               0.0203                0.0331                 0.2958         0.10
 0.20                 -2.9662          0.0536           11.0583   7.4571            4.5329               0.0146                0.0226                 0.2358         0.20
 0.30                 -1.0656          0.0443           10.7624   5.8000            4.2871               0.0108                0.0155                 0.1755         0.30
 0.40                 -0.5439          0.0399           10.4414   5.6000            4.0692               0.0093                0.0136                 0.1360         0.40
 0.50                  0.7238          0.0337            9.8989   4.6571            3.9990               0.0071                0.0101                 0.1086         0.50
 0.60                  1.0790          0.0300            9.3797   3.9429            3.8608               0.0060                0.0083                 0.0858         0.60
 0.80                  0.6815          0.0251            7.8781   2.4000            3.5264               0.0033                0.0042                 0.0506         0.80
 1.00                  0.6588          0.0211            6.8325   2.2571            3.5046               0.0028                0.0035                 0.0368         1.00
 1.25                  0.0567          0.0192            5.5309   1.7143            3.3879               0.0021                0.0023                 0.0233         1.25
 1.50                 -0.3528          0.0169            4.3818   1.4286            3.3945               0.0016                0.0017                 0.0168         1.50
```

Online margin on the harmonic mean

```
       qoe_per_segment  rebuffer_ratio  avg_bitrate_mbps   stalls  switches_per_min  stall_time_fraction  stall_event_fraction  overestimate_fraction  margin_mean
limit                                                                                                                                                             
0.002           0.2283          0.0376            9.2689   4.6286            3.5624               0.0086                0.0141                 0.1537       0.6659
0.005          -0.0353          0.0413            9.8097   5.1429            3.5212               0.0106                0.0167                 0.1697       0.5882
0.010          -0.8267          0.0480           10.2741   7.0571            3.7009               0.0142                0.0231                 0.2104       0.4749
0.020          -3.4799          0.0628           11.0193  10.8286            4.0994               0.0218                0.0381                 0.3225       0.2547
0.040          -7.9009          0.0883           11.7239  17.7429            4.4669               0.0367                0.0631                 0.4727       0.0257
```
