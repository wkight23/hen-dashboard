import os, json, requests, re
from datetime import datetime, date, timedelta
ERCOT_USER = os.environ["ERCOT_USERNAME"]
ERCOT_PASS = os.environ["ERCOT_PASSWORD"]
ERCOT_SUBKEY = os.environ["ERCOT_SUBKEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
BASE = "https://api.ercot.com/api/public-reports"
AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
NOW = datetime.now()
SEASON = {1:"Winter",2:"Winter",3:"Spring",4:"Spring",5:"Spring",6:"Summer",7:"Summer",8:"Summer",9:"Fall",10:"Fall",11:"Fall",12:"Winter"}[NOW.month]
SITE_ZONES = {"RUSSEKST_RN":"WEST","JUNCTION_RN":"WEST","OLNEYTN_RN":"WEST","GRDNE_ESR_RN":"WEST","JDKNS_RN":"WEST","LONESTAR_RN":"WEST","RTLSNAKE_BT":"WEST","SANDLAKE_RN":"WEST","CEDRVALE_RN":"WEST","COYOTSPR_RN":"WEST","FAULKNER_RN":"WEST","SADLBACK_RN":"WEST","TOYAH_RN":"WEST","GOMZ_RN":"WEST","SBEAN_BESS":"WEST","HAMI_BESS_RN":"SOUTH","FTDUNCAN_RN":"SOUTH","CATARINA_B1":"SOUTH","HOLCOMB_RN1":"SOUTH","POTEETS_RN":"SOUTH","FALFUR_RN":"SOUTH","MV_VALV4_RN":"SOUTH","TYNAN_RN":"SOUTH","WLTC_ESR_RN":"SOUTH","PAVLOV_BT_RN":"SOUTH","MAINLAND_RN":"HOUSTON","DIBOL_RN":"NORTH","PAULN_RN":"NORTH","FRMRSVLW_RN":"NORTH","MNWL_BESS_RN":"NORTH","CISC_RN":"NORTH","LFSTH_RN":"NORTH"}
SITE_NAMES = {"RUSSEKST_RN":"Russek","JUNCTION_RN":"Junction","OLNEYTN_RN":"Olney","GRDNE_ESR_RN":"Garden City","JDKNS_RN":"Judkins","LONESTAR_RN":"Lonestar","RTLSNAKE_BT":"Rattlesnake","SANDLAKE_RN":"Sandlake","CEDRVALE_RN":"Cedarvale","COYOTSPR_RN":"Coyote","FAULKNER_RN":"Faulkner","SADLBACK_RN":"Saddleback","TOYAH_RN":"Toyah","GOMZ_RN":"Gomez","SBEAN_BESS":"Screwbean","HAMI_BESS_RN":"Hamilton","FTDUNCAN_RN":"Fort Duncan","CATARINA_B1":"Catarina","HOLCOMB_RN1":"Holcomb","POTEETS_RN":"Poteets","FALFUR_RN":"Falfurrias","MV_VALV4_RN":"Val Verde","TYNAN_RN":"Tynan","WLTC_ESR_RN":"Weil Tract","PAVLOV_BT_RN":"Pavlov","MAINLAND_RN":"Mainland","DIBOL_RN":"Diboll","PAULN_RN":"Pauline","FRMRSVLW_RN":"Farmersville","MNWL_BESS_RN":"Mineral Wells","CISC_RN":"Cisco","LFSTH_RN":"Lufkin South"}
SF_TO_SP = {"Russek":"RUSSEKST_RN","Catarina":"CATARINA_B1","Holcomb":"HOLCOMB_RN1","Hamilton":"HAMI_BESS_RN","FortDuncan":"FTDUNCAN_RN","Junction":"JUNCTION_RN","Judkins":"JDKNS_RN","Saddleback":"SADLBACK_RN","Cedarvale":"CEDRVALE_RN","Toyah":"TOYAH_RN","Coyote":"COYOTSPR_RN","Faulkner":"FAULKNER_RN","GardenCity":"GRDNE_ESR_RN","Gomez":"GOMZ_RN","Lonestar":"LONESTAR_RN","Rattlesnake":"RTLSNAKE_BT","Sandlake":"SANDLAKE_RN","Screwbean":"SBEAN_BESS","ValVerde":"MV_VALV4_RN","Falfurrias":"FALFUR_RN"}
SF_DATA = {'TWINBU-HARGROVE 138KV HARGRO_TWINBU1_1': {'sf': {'Russek': 0.31665, 'Hamilton': 0.0679, 'FortDuncan': 0.04386, 'Gomez': 0.03504}, 'total': 812338.3, 'peak_he': [5, 6, 4], 'hourly': [67031.56, 78042.27, 85676.48, 93412.97, 101422.32, 95386.19, 78245.67, 52048.79, 13496.03, 9337.29, 5147.96, 1781.44, 1755.51, 2254.73, 1723.31, 1844.91, 880.08, 977.51, 4184.01, 6324.09, 12226.18, 18850.77, 28465.14, 51823.09]}, 'VEALMOOR-KOCHTAP 138KV 15060__B': {'sf': {'Judkins': 0.05229, 'Saddleback': 0.0447, 'Cedarvale': 0.04791, 'Toyah': 0.04336, 'Coyote': 0.04786, 'Faulkner': 0.04786, 'GardenCity': 0.05639, 'Gomez': 0.04241, 'Lonestar': 0.04957, 'Rattlesnake': 0.04922, 'Screwbean': 0.04911}, 'total': 294667.84, 'peak_he': [23, 24, 22], 'hourly': [27591.31, 23274.76, 20559.37, 16173.34, 12792.28, 13211.21, 14779.99, 6913.64, 3585.96, 1366.62, 1635.31, 1134.12, 1336.08, 1178.71, 914.18, 1482.47, 2080.56, 4782.57, 7397.81, 10320.53, 18762.76, 31663.08, 37471.54, 34259.64]}, 'LA_PALMA-HAINE_DR 138KV HAINE__LA_PAL1_1': {'sf': {'ValVerde': 0.18556, 'Falfurrias': 0.03922}, 'total': 157434.95, 'peak_he': [17, 16, 18], 'hourly': [2007.36, 1498.5, 955.3, 1179.14, 649.95, 662.18, 1138.03, 1170.9, 2606.9, 4689.33, 5893.81, 8060.67, 10321.91, 12148.7, 14938.22, 18273.92, 19748.9, 17889.71, 11539.64, 7304.47, 5321.6, 4421.88, 2913.09, 2100.84]}, 'LARDVNTH-LASCRUCE 138KV LARDVN_LASCRU1_1': {'sf': {'Catarina': 0.17885, 'Holcomb': 0.29736, 'Hamilton': 0.06158, 'ValVerde': -0.079, 'Falfurrias': -0.09714}, 'total': 150133.74, 'peak_he': [20, 21, 22], 'hourly': [5292.9, 4016.18, 2584.08, 1441.52, 1460.88, 1506.22, 1972.63, 1300.26, 1077.74, 1765.52, 2139.03, 2022.88, 1587.54, 1384.82, 1552.48, 2858.78, 4289.72, 7677.17, 15748.88, 27679.73, 27663.42, 18016.5, 9419.33, 5675.53]}, 'FORTMA-YELWJCKT 138KV FORTMA_YELWJC1_1': {'sf': {'Russek': 0.032, 'Junction': 0.5}, 'total': 103773.93, 'peak_he': [21, 20, 23], 'hourly': [6927.47, 7504.88, 5776.69, 7337.18, 6465.42, 4479.64, 4070.58, 3102.16, 982.11, 163.73, 0.0, 0.0, 0.0, 0.0, 0.0, 6.0, 697.78, 6238.74, 7077.57, 8859.78, 9917.69, 8495.72, 8672.96, 6997.83]}, 'TREADWEL-YELWJCKT 138KV TREADW_YELWJC1_1': {'sf': {'Russek': -0.03187, 'Junction': 0.46755}, 'total': 99801.11, 'peak_he': [17, 18, 19], 'hourly': [2040.61, 1496.75, 1311.53, 1197.23, 802.83, 897.6, 1087.27, 822.49, 1233.12, 2381.19, 4127.3, 5372.08, 5905.86, 7345.69, 8718.37, 9151.0, 10821.32, 10302.42, 9283.54, 6435.89, 2234.67, 2028.78, 2482.7, 2320.87]}, 'SONR-ATSO 69KV ATSO_SONR1_1': {'sf': {'Russek': 0.05}, 'total': 93639.82, 'peak_he': [1, 3, 2], 'hourly': [8003.2, 7850.59, 7882.16, 7830.67, 7086.51, 7565.07, 5873.66, 5270.89, 3777.6, 3998.96, 1519.44, 620.13, 308.09, 216.82, 235.11, 297.52, 162.86, 289.44, 744.93, 1399.59, 2948.97, 4632.99, 7845.21, 7279.41]}, 'OZONA-MIDW 69KV MIDW_OZONA1_1': {'sf': {'Russek': 0.06}, 'total': 89022.35, 'peak_he': [16, 15, 13], 'hourly': [2829.71, 3402.85, 5549.1, 5771.66, 4595.97, 1596.84, 1709.64, 2028.79, 3249.59, 3074.47, 1604.16, 1667.8, 5914.93, 4798.75, 7461.95, 12137.93, 5665.36, 4234.92, 2218.84, 350.0, 349.43, 890.85, 3835.7, 4083.11]}, 'STP-ELMCREEK 345KV STPELM27_1': {'sf': {'Russek': 0.042, 'Catarina': 0.08, 'Holcomb': 0.05473, 'Hamilton': 0.0434, 'FortDuncan': 0.05035, 'Judkins': 0.037, 'Saddleback': 0.039, 'ValVerde': 0.052, 'Falfurrias': 0.03272}, 'total': 89021.72, 'peak_he': [22, 21, 23], 'hourly': [3789.99, 3172.48, 3064.52, 3075.23, 3171.1, 4517.58, 5196.07, 5373.49, 1727.02, 557.12, 454.9, 439.05, 423.35, 429.37, 190.28, 55.57, 707.6, 3364.43, 7098.8, 5392.5, 9584.25, 11626.19, 9016.85, 6593.98]}, 'E_PASP': {'sf': {'Catarina': -0.10938, 'Holcomb': -0.15711, 'Hamilton': -0.03345, 'FortDuncan': -0.06029, 'ValVerde': -0.22122, 'Falfurrias': -0.21512}, 'total': 84322.9, 'peak_he': [20, 19, 18], 'hourly': [1311.99, 791.19, 474.4, 433.31, 368.34, 622.26, 345.87, 317.93, 262.53, 1179.02, 1305.35, 1513.93, 1433.25, 1890.45, 3115.82, 4385.6, 5650.32, 8258.88, 13547.46, 17042.59, 8067.77, 7311.33, 2719.71, 1973.6]}, 'KLNSW-STAGE 138KV 641__A': {'sf': {'Russek': -0.04, 'Judkins': -0.04505, 'Saddleback': -0.04, 'Cedarvale': -0.044, 'Toyah': -0.044, 'Coyote': -0.044, 'Faulkner': -0.044, 'Lonestar': -0.044, 'Rattlesnake': -0.044, 'Sandlake': -0.044, 'Screwbean': -0.044}, 'total': 80643.09, 'peak_he': [22, 23, 24], 'hourly': [5632.42, 5200.56, 4901.54, 4864.88, 4652.85, 4521.74, 4228.25, 3577.69, 2204.32, 1784.27, 1170.4, 927.38, 950.41, 809.15, 725.08, 999.61, 1030.8, 999.21, 2766.44, 4376.23, 4630.51, 7010.36, 6743.45, 5935.54]}, 'LAKENASW-SAMATHIS 69KV LAKENA_SAMATH1_1': {'sf': {'Russek': 0.07252}, 'total': 79252.55, 'peak_he': [1, 4, 24], 'hourly': [11497.71, 8541.15, 6992.86, 9570.23, 7538.91, 6370.11, 2965.11, 0.0, 0.0, 16.54, 107.66, 2073.32, 1309.31, 36.12, 47.38, 12.75, 27.2, 0.0, 0.0, 445.87, 2970.27, 5165.65, 4968.28, 8596.12]}, 'HCKSW 1KV HCKSW_MR2L': {'sf': {'Russek': -0.035, 'Judkins': -0.04, 'Saddleback': -0.04, 'Cedarvale': -0.031, 'Toyah': -0.038, 'Coyote': -0.031, 'Faulkner': -0.031, 'GardenCity': -0.041, 'Gomez': -0.038, 'Lonestar': -0.039, 'Rattlesnake': -0.039, 'Sandlake': -0.039, 'Screwbean': -0.039}, 'total': 69902.77, 'peak_he': [19, 21, 20], 'hourly': [961.86, 686.11, 658.72, 614.98, 640.12, 682.57, 1259.11, 1089.81, 1184.99, 2755.47, 2881.95, 3100.07, 2760.41, 2940.27, 2933.88, 3282.39, 3767.78, 4747.29, 7725.78, 6659.42, 7378.84, 5839.02, 3595.43, 1756.5]}, 'CRTRVLLE-HILGR 138KV 16050__B': {'sf': {'Judkins': 0.046, 'Saddleback': 0.0395, 'Cedarvale': 0.0398, 'Toyah': 0.0363, 'Coyote': 0.0399, 'Faulkner': 0.0399, 'GardenCity': 0.136, 'Gomez': 0.0377, 'Lonestar': 0.0409, 'Rattlesnake': 0.041, 'Sandlake': 0.0399, 'Screwbean': 0.0411}, 'total': 66977.23, 'peak_he': [1, 2, 23], 'hourly': [7020.09, 6266.66, 4919.49, 4259.09, 3567.73, 3435.13, 2862.97, 2765.02, 1893.86, 249.79, 689.63, 517.19, 412.86, 85.78, 751.13, 949.08, 1299.32, 1445.65, 2069.65, 2776.36, 3403.54, 5138.64, 5349.11, 4849.46]}, 'LASCRUCE-MILO 138KV LASCRU_MILO1_1': {'sf': {'Catarina': 0.17261, 'Holcomb': 0.28025, 'Hamilton': 0.07, 'FortDuncan': 0.09648, 'ValVerde': -0.08, 'Falfurrias': -0.097}, 'total': 59751.88, 'peak_he': [20, 19, 21], 'hourly': [2698.34, 2135.24, 2595.03, 2635.43, 2780.0, 2630.49, 2489.77, 2672.6, 1383.99, 642.14, 909.49, 921.82, 696.89, 570.21, 712.37, 1204.27, 2156.75, 3398.77, 5910.35, 6139.76, 4375.1, 4356.49, 2805.09, 2931.49]}, 'NLARSW-PILONCIL 138KV NLARSW_PILONC1_1': {'sf': {'Catarina': 0.26, 'Holcomb': -0.09, 'Hamilton': 0.08633, 'FortDuncan': 0.12, 'ValVerde': -0.06, 'Falfurrias': -0.0591}, 'total': 59654.53, 'peak_he': [24, 1, 2], 'hourly': [5617.55, 5546.82, 4468.11, 3991.56, 3535.61, 4411.91, 1968.52, 1849.97, 1163.11, 779.73, 536.63, 449.55, 548.07, 520.62, 541.11, 717.18, 1103.9, 1406.76, 1016.29, 2775.17, 2575.22, 2936.22, 4839.01, 6355.91]}, 'LNGSW-PRLSW 345KV 6965__A': {'sf': {'Russek': 0.07, 'Judkins': 0.21329, 'Saddleback': 0.20412, 'Cedarvale': 0.209, 'Coyote': 0.209, 'Faulkner': 0.209, 'GardenCity': 0.1175, 'Gomez': 0.1981, 'Lonestar': 0.212, 'Rattlesnake': 0.2139, 'Sandlake': 0.209, 'Screwbean': 0.2149}, 'total': 56393.44, 'peak_he': [1, 2, 24], 'hourly': [4609.85, 4522.05, 4308.79, 3904.78, 3499.42, 3088.33, 2084.55, 1380.77, 580.35, 446.24, 699.9, 787.08, 835.66, 827.62, 821.14, 1045.78, 1090.38, 1627.47, 1704.78, 2261.65, 3222.73, 4110.84, 4426.32, 4506.96]}, 'SNDHT-WLFSW 138KV 6345__L': {'sf': {'Judkins': -0.44871, 'Saddleback': 0.071, 'Cedarvale': 0.072, 'Toyah': 0.054, 'Coyote': 0.073, 'Faulkner': 0.076, 'Gomez': 0.04977, 'Lonestar': 0.072, 'Rattlesnake': 0.0828, 'Sandlake': 0.0736, 'Screwbean': 0.0786}, 'total': 54270.9, 'peak_he': [4, 2, 1], 'hourly': [7186.95, 7911.17, 6813.76, 8124.32, 7162.87, 3676.98, 4253.62, 2049.72, 231.58, 28.21, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 189.45, 793.09, 2653.19, 3195.99]}, 'PALOUSE-WOLFCAMP 138KV PALOUS_WOLFCA1_1': {'sf': {'Russek': 0.29986, 'Hamilton': 0.03549, 'Saddleback': -0.0323, 'Cedarvale': -0.03144, 'Toyah': -0.0371, 'Coyote': -0.0316, 'Faulkner': -0.0316, 'Gomez': -0.0378, 'Sandlake': -0.031}, 'total': 49238.51, 'peak_he': [18, 17, 16], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 105.29, 407.76, 596.71, 1520.39, 2233.12, 3432.43, 4606.39, 5094.25, 5834.43, 5859.12, 6010.54, 6255.62, 4731.67, 2377.63, 173.16, 0.0, 0.0, 0.0]}, 'KLNSW-HHSTH 138KV 630__B': {'sf': {'Russek': -0.05, 'Judkins': -0.048, 'Saddleback': -0.048, 'Cedarvale': -0.048, 'Toyah': -0.048, 'Coyote': -0.048, 'Faulkner': -0.048, 'GardenCity': -0.048, 'Gomez': -0.048, 'Lonestar': -0.048, 'Rattlesnake': -0.048, 'Sandlake': -0.048, 'Screwbean': -0.048}, 'total': 42121.0, 'peak_he': [22, 23, 2], 'hourly': [2347.35, 2481.2, 2411.82, 2213.21, 1980.95, 1981.37, 1947.01, 2348.68, 1511.67, 1248.43, 914.67, 717.31, 672.93, 710.72, 569.06, 446.46, 759.77, 1327.29, 2327.88, 2284.31, 2469.9, 3094.09, 2879.17, 2475.75]}, 'WCRYSTS-CARIZOS 69KV WCR_CARI_1': {'sf': {'Catarina': -0.055, 'Hamilton': 0.126, 'FortDuncan': 0.19}, 'total': 39682.54, 'peak_he': [7, 8, 5], 'hourly': [941.77, 2144.9, 2161.03, 2683.65, 4065.23, 3743.47, 7401.42, 5101.41, 971.47, 109.52, 89.78, 5.07, 0.0, 0.0, 0.0, 0.0, 0.0, 303.31, 1275.14, 1452.34, 2591.33, 2642.97, 1197.48, 801.25]}, 'LOBO-LARDVNTH 138KV LARDVN_LOBO2_1': {'sf': {'Catarina': 0.21816, 'Holcomb': 0.32386, 'Hamilton': 0.07, 'FortDuncan': 0.07, 'ValVerde': -0.07, 'Falfurrias': -0.103}, 'total': 37951.02, 'peak_he': [22, 19, 21], 'hourly': [1612.49, 1294.51, 880.24, 569.87, 429.57, 453.71, 562.4, 596.74, 584.41, 659.64, 921.51, 759.11, 742.65, 932.14, 1077.88, 1433.85, 2046.02, 3113.17, 3340.8, 3034.76, 3335.27, 4415.43, 2989.97, 2164.88]}, 'STP-WAP 345KV STPWAP39_1': {'sf': {'Catarina': -0.085, 'Holcomb': -0.09462, 'Hamilton': -0.05, 'FortDuncan': -0.07, 'Junction': -0.034, 'ValVerde': -0.099, 'Falfurrias': -0.099}, 'total': 33834.4, 'peak_he': [17, 16, 13], 'hourly': [1.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 93.47, 583.51, 1310.42, 2267.37, 4378.74, 4131.06, 4376.04, 5652.8, 6104.37, 4051.3, 867.58, 16.72, 0.0, 0.0, 0.0, 0.0]}, 'ESCONDID-GANSO 138KV ESCOND_GANSO1_1': {'sf': {'Russek': 0.05, 'Catarina': -0.094, 'Holcomb': -0.044, 'Hamilton': 0.4035, 'FortDuncan': -0.2614}, 'total': 33325.75, 'peak_he': [8, 9, 1], 'hourly': [2272.75, 1823.59, 1882.15, 1906.0, 1986.73, 1528.84, 1608.22, 2658.7, 2300.74, 1011.41, 656.93, 1085.99, 735.09, 644.99, 605.74, 479.31, 1386.94, 1190.33, 825.08, 858.59, 1303.51, 1002.98, 1527.27, 2043.87]}, 'MASN-KATEMCY 69KV KATEMC_MASN1_1': {'sf': {'Junction': 0.251}, 'total': 32915.57, 'peak_he': [19, 18, 23], 'hourly': [462.62, 1.95, 37.28, 31.56, 429.36, 146.9, 338.39, 3483.54, 2612.74, 1263.97, 760.92, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4537.22, 4802.99, 2138.24, 2877.97, 3484.48, 3507.62, 1997.82]}, 'BCESW-SNDSW 345KV 421__A': {'sf': {'Catarina': 0.093, 'Holcomb': 0.11, 'Hamilton': 0.07, 'FortDuncan': 0.09, 'Junction': 0.032, 'Judkins': -0.045, 'Saddleback': -0.04, 'Cedarvale': -0.04, 'Toyah': -0.035, 'Coyote': -0.04, 'Faulkner': -0.04, 'GardenCity': -0.048, 'Gomez': -0.0365, 'Lonestar': -0.041, 'Rattlesnake': -0.041, 'Sandlake': -0.04, 'Screwbean': -0.0415, 'ValVerde': 0.11, 'Falfurrias': 0.096}, 'total': 32240.3, 'peak_he': [17, 18, 16], 'hourly': [288.26, 253.67, 253.78, 156.02, 59.26, 75.07, 205.46, 296.05, 629.96, 1399.44, 1396.89, 1976.95, 2257.87, 2949.19, 3758.9, 4072.73, 4766.5, 4503.34, 1598.82, 233.58, 279.89, 235.08, 272.5, 321.09]}, 'ODESA-ODNTH 138KV 6513__A': {'sf': {'Saddleback': 0.082, 'Cedarvale': 0.0885, 'Toyah': 0.0599, 'Coyote': 0.086, 'Faulkner': 0.086, 'Gomez': 0.0476, 'Lonestar': 0.1, 'Rattlesnake': 0.094, 'Sandlake': 0.088, 'Screwbean': 0.094}, 'total': 32001.33, 'peak_he': [23, 5, 22], 'hourly': [2132.45, 1598.0, 1834.9, 2120.77, 2788.32, 2589.66, 2454.6, 1624.0, 58.4, 88.81, 98.94, 120.61, 128.99, 54.63, 0.06, 1.04, 2.51, 739.1, 2228.19, 2077.62, 2134.42, 2610.45, 2811.61, 1703.25]}, 'MGSES-CATSW 345KV 6945__A': {'sf': {'Russek': 0.1, 'Hamilton': 0.063, 'FortDuncan': 0.039, 'Judkins': 0.3, 'Saddleback': 0.27037, 'Cedarvale': 0.2, 'Toyah': 0.199, 'Coyote': 0.2, 'Faulkner': 0.2, 'GardenCity': 0.242, 'Gomez': 0.199, 'Lonestar': 0.21, 'Rattlesnake': 0.21, 'Sandlake': 0.2, 'Screwbean': 0.21}, 'total': 31442.57, 'peak_he': [23, 19, 20], 'hourly': [1614.56, 1865.31, 1860.67, 1941.16, 1443.57, 1847.13, 1313.93, 1093.3, 742.74, 241.84, 424.34, 308.61, 171.39, 27.01, 53.78, 167.27, 797.88, 1641.74, 2939.11, 2708.21, 1879.05, 1197.21, 3335.75, 1827.01]}, 'LNGSW-CONSW 345KV 6056__A': {'sf': {'Russek': 0.056, 'Hamilton': 0.037, 'Judkins': 0.233, 'Saddleback': 0.2, 'Cedarvale': 0.2, 'Toyah': 0.19, 'Coyote': 0.2, 'Faulkner': 0.2, 'GardenCity': 0.11, 'Gomez': 0.19, 'Lonestar': 0.21, 'Rattlesnake': 0.21, 'Sandlake': 0.209, 'Screwbean': 0.21}, 'total': 30989.79, 'peak_he': [1, 2, 24], 'hourly': [4086.86, 3745.26, 3211.53, 2996.59, 2905.08, 2210.82, 1592.44, 672.79, 254.66, 266.87, 174.72, 177.29, 145.49, 141.08, 122.16, 83.53, 83.41, 113.11, 546.52, 356.42, 556.64, 1059.67, 2265.1, 3221.75]}, 'BIG_FOOT-PLEASANT 138KV BIG_FO_PLEASA1_1': {'sf': {'Catarina': -0.049, 'Hamilton': -0.058, 'FortDuncan': -0.06}, 'total': 26156.41, 'peak_he': [16, 13, 15], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 51.2, 888.78, 1963.97, 3301.9, 3954.66, 3422.34, 3690.71, 3977.51, 3264.92, 1465.73, 173.85, 0.84, 0.0, 0.0, 0.0, 0.0]}, 'GN-PZ 138KV GN_PZ_08_A': {'sf': {'Catarina': -0.1, 'Holcomb': -0.1, 'FortDuncan': -0.1}, 'total': 25619.24, 'peak_he': [16, 14, 17], 'hourly': [66.68, 32.62, 2.43, 0.55, 0.0, 0.0, 1.8, 0.86, 76.94, 560.75, 1094.6, 1812.68, 3093.01, 3365.08, 3201.45, 5203.15, 3306.83, 2493.54, 715.96, 146.14, 128.89, 91.6, 86.7, 136.98]}, 'FTSSW-VENSW 345KV 35050__B': {'sf': {'Catarina': -0.0569, 'Holcomb': -0.06, 'Hamilton': -0.037, 'FortDuncan': -0.047, 'Junction': -0.041, 'ValVerde': -0.06, 'Falfurrias': -0.06}, 'total': 24101.09, 'peak_he': [16, 15, 17], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.09, 285.75, 648.94, 1402.71, 2246.81, 2739.23, 2962.88, 3722.32, 4126.8, 3540.85, 2086.74, 332.97, 0.0, 0.0, 0.0, 0.0, 0.0]}, 'MILLER-HENLY 138KV 415T415_1': {'sf': {'Junction': -0.11}, 'total': 23333.33, 'peak_he': [17, 18, 19], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2333.33, 7000.0, 7000.0, 6416.67, 583.33, 0.0, 0.0, 0.0, 0.0]}, 'ASHERTON-CATARINA 138KV ASHERT_CATARI1_1': {'sf': {'Catarina': 0.76982, 'Holcomb': 0.17245, 'Hamilton': -0.09, 'FortDuncan': -0.116}, 'total': 23033.53, 'peak_he': [13, 12, 14], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 333.66, 1115.4, 2020.27, 2963.52, 3376.63, 2919.27, 2602.16, 2808.89, 2593.83, 1548.22, 693.24, 58.44, 0.0, 0.0, 0.0, 0.0]}, 'JEWET-BBSES 345KV 50__A': {'sf': {'Russek': 0.04, 'Catarina': -0.04, 'Holcomb': -0.05, 'Judkins': 0.04, 'Saddleback': 0.04, 'Cedarvale': 0.04, 'Toyah': 0.04, 'Coyote': 0.04, 'Faulkner': 0.04, 'GardenCity': 0.04, 'Gomez': 0.04, 'Lonestar': 0.04, 'Rattlesnake': 0.04, 'Sandlake': 0.04, 'Screwbean': 0.04, 'ValVerde': -0.05, 'Falfurrias': -0.05}, 'total': 22370.98, 'peak_he': [21, 20, 8], 'hourly': [261.37, 526.49, 538.9, 302.12, 625.63, 431.19, 677.85, 3128.83, 273.97, 3.95, 0.0, 0.0, 0.0, 0.0, 18.18, 133.11, 349.27, 357.71, 2453.78, 4349.93, 4637.0, 2959.45, 256.73, 85.52]}, 'PILONCIL-CATARINA 138KV CATARI_PILONC1_1': {'sf': {'Catarina': 0.337, 'Holcomb': -0.098}, 'total': 22056.9, 'peak_he': [22, 20, 21], 'hourly': [910.5, 1110.71, 981.72, 987.65, 935.87, 1262.87, 1203.46, 998.89, 663.6, 515.84, 231.61, 0.24, 0.0, 0.0, 0.0, 366.22, 418.93, 647.69, 1209.39, 2127.71, 2105.86, 2514.6, 1771.55, 1091.99]}, 'MV_BURNS-MV_HBRG4 138KV BURNS_HEIDLBRG_1': {'sf': {'ValVerde': 0.15343}, 'total': 21330.38, 'peak_he': [17, 18, 19], 'hourly': [113.87, 3.77, 146.43, 37.55, 0.0, 0.0, 0.0, 0.0, 0.0, 16.29, 393.46, 739.86, 957.48, 1274.3, 1942.22, 2435.39, 3596.77, 3322.57, 3266.36, 1218.55, 631.1, 475.07, 449.24, 310.1]}, 'SAMSW-VENSW 345KV 35055__A': {'sf': {'Catarina': -0.053, 'Holcomb': -0.056, 'Hamilton': -0.035, 'FortDuncan': -0.044, 'Junction': -0.039, 'ValVerde': -0.056, 'Falfurrias': -0.056}, 'total': 20889.84, 'peak_he': [11, 12, 13], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 317.47, 2511.18, 3425.87, 3383.89, 3195.6, 2827.63, 2197.21, 1730.95, 785.61, 394.73, 119.7, 0.0, 0.0, 0.0, 0.0, 0.0]}, 'I_FW_N': {'sf': {'Russek': 0.09, 'Hamilton': 0.034, 'Judkins': 0.1566, 'Saddleback': 0.1374, 'Cedarvale': 0.13, 'Toyah': 0.12, 'Coyote': 0.138, 'Faulkner': 0.134, 'GardenCity': 0.158, 'Gomez': 0.133, 'Lonestar': 0.143, 'Rattlesnake': 0.142, 'Sandlake': 0.137, 'Screwbean': 0.141}, 'total': 20645.72, 'peak_he': [5, 6, 4], 'hourly': [1099.23, 1401.06, 1751.5, 1826.9, 2151.59, 1942.22, 1414.12, 1533.12, 854.4, 112.26, 84.83, 55.38, 57.12, 53.85, 92.8, 41.21, 131.4, 82.22, 151.14, 465.94, 997.42, 1365.76, 1634.32, 1345.93]}, 'YELWJCKT-HEXT 69KV HEXT_YELWJC1_1': {'sf': {'Junction': 0.059}, 'total': 18859.01, 'peak_he': [14, 17, 12], 'hourly': [466.98, 629.39, 146.79, 97.33, 206.72, 117.15, 209.53, 448.5, 1802.06, 581.31, 1468.79, 2058.57, 1612.21, 2116.11, 1945.01, 1794.97, 2086.8, 0.0, 0.0, 163.64, 169.94, 237.13, 266.81, 233.27]}, 'YELWJCKT-FORTMA 138KV FORTMA_YELWJC1_1': {'sf': {'Russek': -0.03, 'Junction': -0.5}, 'total': 18780.08, 'peak_he': [7, 6, 5], 'hourly': [838.61, 708.63, 866.54, 1018.41, 1120.39, 1514.25, 1695.8, 998.7, 986.58, 974.57, 418.53, 462.55, 425.85, 511.04, 689.88, 584.12, 1013.98, 419.11, 329.65, 344.62, 809.24, 772.81, 675.08, 601.14]}, 'MADDUX-TREADWEL 138KV MADDUX_TREADW1_1': {'sf': {'Junction': 0.39252, 'Judkins': -0.035, 'Saddleback': -0.035, 'Cedarvale': -0.035, 'Toyah': -0.035, 'Coyote': -0.035, 'Faulkner': -0.035, 'GardenCity': -0.035, 'Gomez': -0.035, 'Lonestar': -0.035, 'Rattlesnake': -0.035, 'Sandlake': -0.035, 'Screwbean': -0.035}, 'total': 18278.19, 'peak_he': [17, 18, 16], 'hourly': [184.3, 145.59, 123.73, 127.0, 33.79, 73.4, 147.31, 100.89, 17.41, 171.62, 276.95, 617.72, 1018.32, 1359.94, 1815.76, 2318.53, 3327.37, 2557.19, 1668.52, 1087.54, 314.6, 320.98, 258.74, 210.99]}, 'MDO-PHR 345KV MDOPHR99_A': {'sf': {'Catarina': -0.062, 'Holcomb': -0.067, 'Hamilton': -0.044, 'FortDuncan': -0.05, 'Junction': -0.032, 'ValVerde': -0.1, 'Falfurrias': -0.075}, 'total': 18172.47, 'peak_he': [16, 14, 15], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.08, 108.39, 337.07, 644.84, 1512.03, 2162.1, 2953.72, 2648.96, 3552.94, 2252.6, 1621.71, 368.74, 4.29, 0.0, 0.0, 0.0, 0.0]}, 'RIOHONDO-MV_BURNS 138KV BURNS_RIOHONDO_1': {'sf': {'ValVerde': 0.1976, 'Falfurrias': 0.047}, 'total': 16376.64, 'peak_he': [18, 17, 19], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 132.35, 299.2, 530.82, 888.61, 1066.58, 1942.0, 3534.94, 4167.81, 2881.25, 884.23, 48.85, 0.0, 0.0, 0.0]}, 'HAMILTON-MAVERICK 138KV HAMILT_MAVERI1_1': {'sf': {'Russek': -0.035, 'Catarina': 0.072, 'Holcomb': 0.034, 'Hamilton': -0.56, 'FortDuncan': 0.19612}, 'total': 15943.21, 'peak_he': [17, 20, 21], 'hourly': [491.69, 349.46, 336.38, 436.87, 354.78, 299.71, 237.0, 422.32, 489.3, 620.31, 482.48, 771.43, 749.78, 707.89, 756.73, 1006.51, 1172.48, 976.68, 888.63, 1162.49, 1101.57, 992.08, 555.19, 581.45]}, 'MAXWELL-HAMILTON 138KV HAMILT_MAXWEL1_1': {'sf': {'Catarina': 0.057, 'Hamilton': 0.22977, 'FortDuncan': 0.142}, 'total': 14519.92, 'peak_he': [2, 24, 1], 'hourly': [1371.62, 1628.62, 1351.71, 1066.23, 925.01, 592.0, 680.58, 541.95, 414.63, 170.11, 141.42, 54.33, 13.92, 29.66, 28.3, 53.84, 74.95, 190.22, 636.63, 646.34, 541.79, 708.72, 1178.57, 1478.77]}, 'BLESSING 345KV BLESSING_1382': {'sf': {'Holcomb': 0.041, 'ValVerde': 0.063}, 'total': 14518.22, 'peak_he': [22, 9, 7], 'hourly': [192.76, 364.64, 411.69, 498.11, 939.07, 1226.81, 1545.14, 1376.78, 1649.64, 1228.11, 533.69, 192.13, 215.83, 149.05, 116.94, 34.83, 133.54, 186.3, 199.82, 181.49, 789.38, 1742.85, 453.67, 155.95]}, 'CARVER-TINSLEY 138KV CARVER_TINSLE1_1': {'sf': {'Russek': -0.075, 'Catarina': 0.094, 'Holcomb': 0.045, 'Hamilton': 0.32323, 'FortDuncan': 0.21}, 'total': 14200.33, 'peak_he': [21, 20, 22], 'hourly': [625.15, 553.62, 320.19, 364.32, 582.27, 201.81, 66.6, 75.0, 165.94, 672.82, 846.51, 593.15, 501.89, 220.39, 231.33, 799.32, 766.59, 771.24, 366.03, 1396.82, 1474.42, 996.72, 888.65, 719.55]}, 'LAREDO-DEL_MAR 138KV DEL_MA_LAREDO1_1': {'sf': {'Catarina': 0.035, 'Holcomb': 0.06}, 'total': 12390.2, 'peak_he': [23, 24, 22], 'hourly': [1631.85, 594.25, 240.53, 10.03, 0.0, 48.1, 16.4, 0.0, 61.85, 379.63, 409.9, 240.13, 159.39, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2034.64, 3808.83, 2754.67]}, 'W_BATESV-UVALDE 138KV UVALDE_W_BATE1_1': {'sf': {'Catarina': -0.14975, 'Holcomb': -0.06, 'Hamilton': 0.27526, 'FortDuncan': 0.29993}, 'total': 12090.77, 'peak_he': [22, 4, 21], 'hourly': [0.0, 21.33, 30.48, 1296.03, 688.97, 223.95, 481.81, 597.29, 632.92, 809.61, 332.14, 170.1, 39.68, 28.32, 41.89, 362.42, 991.13, 462.08, 1168.59, 782.43, 1171.47, 1602.25, 82.85, 73.03]}, 'CPSES-MBDSW 345KV 6033__A': {'sf': {'Russek': -0.06, 'Hamilton': -0.034, 'Junction': -0.045, 'Judkins': -0.059, 'Saddleback': -0.058, 'Cedarvale': -0.058, 'Toyah': -0.057, 'Coyote': -0.058, 'Faulkner': -0.058, 'GardenCity': -0.058, 'Gomez': -0.058, 'Lonestar': -0.058, 'Rattlesnake': -0.058, 'Sandlake': -0.058, 'Screwbean': -0.058}, 'total': 11040.17, 'peak_he': [20, 1, 7], 'hourly': [719.41, 568.46, 566.01, 519.16, 575.6, 635.09, 706.34, 289.17, 171.8, 223.48, 238.55, 233.05, 251.41, 241.25, 268.81, 215.43, 407.07, 405.68, 436.28, 720.93, 670.11, 625.03, 666.14, 685.91]}, 'ZEN-THW 345KV THWZEN71_A': {'sf': {'Russek': -0.051, 'Hamilton': -0.033, 'Junction': -0.042, 'Judkins': -0.055, 'Saddleback': -0.054, 'Cedarvale': -0.054, 'Toyah': -0.053, 'Coyote': -0.054, 'Faulkner': -0.054, 'GardenCity': -0.056, 'Gomez': -0.054, 'Lonestar': -0.054, 'Rattlesnake': -0.054, 'Sandlake': -0.054, 'Screwbean': -0.054}, 'total': 10819.9, 'peak_he': [15, 14, 16], 'hourly': [0.64, 0.12, 0.69, 2.3, 0.0, 0.0, 22.67, 33.19, 359.24, 685.33, 948.4, 1115.01, 1404.91, 1542.76, 1566.45, 1461.54, 1138.1, 394.26, 43.37, 9.34, 9.9, 10.85, 37.64, 33.19]}, 'LNGSW-CONSW 345KV 6056__Z': {'sf': {'Russek': 0.08513, 'Hamilton': 0.034, 'Judkins': 0.21466, 'Saddleback': 0.2, 'Cedarvale': 0.2, 'Toyah': 0.2, 'Coyote': 0.2, 'Faulkner': 0.2, 'GardenCity': 0.08, 'Gomez': 0.2, 'Lonestar': 0.2, 'Rattlesnake': 0.2, 'Sandlake': 0.2, 'Screwbean': 0.2}, 'total': 9688.18, 'peak_he': [24, 1, 3], 'hourly': [1339.93, 841.77, 1008.99, 731.36, 657.2, 585.68, 589.9, 391.35, 1.58, 0.0, 0.0, 0.0, 0.0, 0.0, 1.55, 2.07, 0.83, 0.0, 141.79, 204.77, 394.55, 464.12, 898.98, 1431.76]}, 'NORTMC-CROSSOVE 138KV CROSSO_NORTMC1_1': {'sf': {'Russek': 0.284, 'Gomez': -0.035}, 'total': 8837.72, 'peak_he': [19, 17, 16], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 39.81, 10.61, 193.52, 476.05, 815.3, 1194.7, 1489.93, 1546.13, 1376.95, 1583.76, 110.96, 0.0, 0.0, 0.0, 0.0]}, 'WESTEX': {'sf': {'Russek': -0.66, 'Catarina': 0.07514, 'Holcomb': 0.13067, 'Hamilton': -0.23, 'FortDuncan': -0.07, 'Junction': -0.3, 'Judkins': -0.718, 'Saddleback': -0.716, 'Cedarvale': -0.71, 'Toyah': -0.71, 'Coyote': -0.71, 'Faulkner': -0.71, 'GardenCity': -0.71, 'Gomez': -0.71, 'Lonestar': -0.71, 'Rattlesnake': -0.71, 'Sandlake': -0.71, 'Screwbean': -0.71, 'ValVerde': 0.15332, 'Falfurrias': 0.15}, 'total': 8701.73, 'peak_he': [20, 19, 12], 'hourly': [305.77, 249.86, 192.79, 152.03, 148.14, 170.43, 204.97, 284.51, 250.59, 377.52, 516.63, 532.59, 469.9, 437.06, 463.27, 492.54, 504.42, 463.31, 543.96, 550.41, 345.63, 311.2, 362.19, 372.01]}, 'PRLSW-CONSW 345KV 6960__A': {'sf': {'Russek': 0.11076, 'Hamilton': 0.0458, 'Judkins': 0.29043, 'Saddleback': 0.2337, 'Cedarvale': 0.233, 'Toyah': 0.2, 'Coyote': 0.235, 'Faulkner': 0.235, 'GardenCity': 0.135, 'Gomez': 0.228, 'Lonestar': 0.244, 'Rattlesnake': 0.246, 'Sandlake': 0.234, 'Screwbean': 0.245}, 'total': 8553.5, 'peak_he': [2, 4, 1], 'hourly': [690.68, 913.32, 566.36, 692.95, 655.64, 433.52, 312.18, 185.38, 138.07, 180.76, 218.65, 141.86, 50.81, 46.44, 65.94, 55.31, 4.46, 318.76, 393.73, 267.11, 481.63, 609.67, 513.09, 617.18]}, 'DOW-OAS 345KV DOWOAS18_A': {'sf': {'Catarina': -0.0722, 'Holcomb': -0.0768, 'Hamilton': -0.048, 'FortDuncan': -0.0599, 'Junction': -0.034, 'ValVerde': -0.0823, 'Falfurrias': -0.081}, 'total': 8240.51, 'peak_he': [14, 16, 15], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 12.28, 103.27, 347.58, 707.75, 1157.39, 1481.45, 1161.23, 1166.15, 1051.01, 912.0, 140.4, 0.0, 0.0, 0.0, 0.0, 0.0]}, 'VALEXP': {'sf': {'ValVerde': -0.98239}, 'total': 8226.78, 'peak_he': [4, 3, 5], 'hourly': [399.38, 518.39, 696.91, 718.28, 687.65, 420.56, 390.56, 411.85, 126.06, 58.49, 29.41, 54.91, 53.22, 64.29, 70.02, 93.44, 266.73, 559.7, 595.21, 527.86, 384.74, 418.65, 349.99, 330.48]}, 'BANDER-MASOCR 138KV 583T583_1': {'sf': {'Junction': -0.08}, 'total': 7382.61, 'peak_he': [16, 19, 18], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 84.58, 146.97, 418.74, 190.76, 313.15, 1109.71, 1286.89, 1136.01, 1253.05, 1270.56, 97.05, 0.0, 0.0, 38.59, 36.55]}, 'ZEN-THW 345KV THWZEN98_A': {'sf': {'Russek': -0.072, 'Junction': -0.035, 'Judkins': -0.046, 'Saddleback': -0.043, 'Cedarvale': -0.044, 'Toyah': -0.042, 'Coyote': -0.044, 'Faulkner': -0.044, 'GardenCity': -0.048, 'Gomez': -0.043, 'Lonestar': -0.044, 'Rattlesnake': -0.044, 'Sandlake': -0.044, 'Screwbean': -0.044}, 'total': 7124.47, 'peak_he': [14, 15, 16], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 9.73, 70.24, 108.05, 430.43, 586.6, 654.15, 711.33, 1213.93, 953.06, 759.19, 584.9, 370.49, 303.76, 191.08, 102.21, 3.01, 66.5, 5.81]}, 'COLETO CREEK-VICTORIA 138KV COLETO_VICTOR2': {'sf': {'Holcomb': -0.037, 'ValVerde': -0.091, 'Falfurrias': -0.088}, 'total': 6622.44, 'peak_he': [20, 22, 21], 'hourly': [328.54, 399.76, 211.03, 237.85, 108.36, 10.8, 18.63, 0.33, 1.57, 59.39, 134.48, 102.48, 161.4, 216.4, 206.62, 472.99, 429.71, 357.27, 513.7, 797.81, 533.2, 555.47, 499.84, 264.81]}, 'TMPSW-TMPCR 345KV 315__A': {'sf': {'Catarina': -0.0932, 'Holcomb': -0.0997, 'Hamilton': -0.05, 'FortDuncan': -0.0737, 'Junction': -0.061, 'GardenCity': 0.032, 'ValVerde': -0.0991, 'Falfurrias': -0.099}, 'total': 6604.19, 'peak_he': [21, 20, 4], 'hourly': [537.33, 502.08, 503.4, 628.49, 423.75, 55.46, 7.97, 1.13, 2.41, 4.71, 11.62, 18.76, 87.43, 22.01, 0.0, 46.05, 3.53, 123.72, 498.52, 714.86, 1368.75, 571.11, 218.81, 252.29]}, 'GANSO-MAVERICK 138KV GANSO_MAVERI1_1': {'sf': {'Catarina': -0.09232, 'Holcomb': -0.04424, 'Hamilton': 0.40193, 'Gomez': 0.03}, 'total': 6314.84, 'peak_he': [4, 6, 5], 'hourly': [80.19, 504.65, 519.83, 920.93, 803.16, 883.55, 477.4, 519.92, 485.09, 206.6, 275.08, 131.17, 13.62, 0.87, 0.0, 7.02, 146.1, 10.1, 146.16, 158.7, 9.05, 15.64, 0.01, 0.0]}, 'TNFXTAIL-FLAT_TOP 138KV 138_FLT_FXT_1': {'sf': {'Saddleback': 0.326, 'Cedarvale': 0.1296, 'Toyah': -0.1, 'Coyote': 0.201, 'Faulkner': 0.201, 'Gomez': -0.061, 'Lonestar': 0.096, 'Rattlesnake': 0.086, 'Sandlake': 0.117, 'Screwbean': 0.079}, 'total': 6210.06, 'peak_he': [17, 16, 15], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 35.7, 408.95, 620.48, 780.93, 760.18, 740.94, 782.2, 787.55, 842.48, 444.95, 5.7, 0.0, 0.0, 0.0, 0.0, 0.0]}, 'MAVERICK-HAMILTON 138KV HAMILT_MAVERI1_1': {'sf': {'Russek': 0.05256, 'Catarina': -0.08936, 'Holcomb': -0.0377, 'Hamilton': 0.4028, 'FortDuncan': -0.25822}, 'total': 5230.46, 'peak_he': [2, 4, 3], 'hourly': [725.75, 1151.65, 937.69, 1075.1, 0.0, 0.0, 11.75, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 116.26, 259.39, 95.37, 0.0, 69.0, 344.07, 444.43]}, 'SMITHERS-BI 345KV BI_SMR98_A': {'sf': {'Catarina': -0.03961, 'Holcomb': -0.04352, 'FortDuncan': -0.326, 'ValVerde': -0.049, 'Falfurrias': -0.048}, 'total': 5229.02, 'peak_he': [19, 18, 17], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.49, 41.95, 116.31, 197.46, 416.6, 275.95, 511.87, 590.34, 737.91, 933.73, 1278.37, 125.04, 0.0, 0.0, 0.0, 0.0]}, 'DOWNIES-MOORE 138KV 2585_1': {'sf': {'Catarina': -0.06, 'Hamilton': -0.15515, 'FortDuncan': -0.18205}, 'total': 5209.02, 'peak_he': [14, 16, 15], 'hourly': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 125.93, 368.42, 623.28, 1056.53, 1008.82, 1042.41, 727.44, 256.19, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}, 'ELGISW-BUTLER 138KV 203T260_1': {'sf': {'Catarina': 0.04196, 'Holcomb': 0.04516, 'FortDuncan': 0.034, 'ValVerde': 0.046, 'Falfurrias': 0.045}, 'total': 5037.87, 'peak_he': [18, 16, 17], 'hourly': [18.26, 8.08, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 21.97, 92.35, 362.5, 448.41, 497.95, 562.46, 692.18, 676.91, 739.95, 638.91, 154.39, 31.54, 37.7, 28.61, 25.7]}}
ZONE_HUBS = {"WEST":"LZ_WEST","SOUTH":"LZ_SOUTH","NORTH":"LZ_NORTH","HOUSTON":"LZ_HOUSTON"}
ALL_NODES = list(SITE_ZONES.keys()) + list(ZONE_HUBS.values())
print("Authenticating with ERCOT...")
auth_resp = requests.post(AUTH_URL, data={"username":ERCOT_USER,"password":ERCOT_PASS,"grant_type":"password","scope":"openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access","client_id":"fec253ea-0d06-4272-a5e6-b478baeecd70","response_type":"id_token"})
token = auth_resp.json().get("id_token","")
hdrs = {"Authorization":"Bearer "+token,"Ocp-Apim-Subscription-Key":ERCOT_SUBKEY}
def eg(path,date_str=None,size=500):
    d=date_str or TODAY
    try:
        r=requests.get(BASE+"/"+path+"?deliveryDateFrom="+d+"&deliveryDateTo="+d+"&size="+str(size),headers=hdrs,timeout=30)
        return r.json() if r.ok else {}
    except:
        return {}
print("Fetching ERCOT data...")
wind_data=eg("np4-742-cd/wpp_hrly_actual_fcast_geo")
load_data=eg("np3-565-cd/lf_by_model_weather_zone")
solar_data=eg("np4-737-cd/spp_hrly_avrg_actl_fcast")
shadow_data=eg("np4-191-cd/dam_shadow_prices")
print("Fetching DA prices...")
da_prices={}
try:
    da_resp=requests.get(BASE+"/np4-190-cd/dam_stlmt_pnt_prices?deliveryDateFrom="+TODAY+"&deliveryDateTo="+TODAY+"&size=2000",headers=hdrs,timeout=30)
    if da_resp.ok:
        da_json=da_resp.json()
        da_fields=da_json.get("fields",[])
        da_rows=da_json.get("data",[])
        sp_col=next((f["cardinality"]-1 for f in da_fields if "settlementPoint" in f.get("name","")),2)
        he_col=next((f["cardinality"]-1 for f in da_fields if "deliveryHour" in f.get("name","") or "hourEnding" in f.get("name","")),3)
        pr_col=next((f["cardinality"]-1 for f in da_fields if "Price" in f.get("name","")),4)
        print("DA cols: sp="+str(sp_col)+" he="+str(he_col)+" pr="+str(pr_col)+" rows="+str(len(da_rows)))
        for item in da_rows:
            if not isinstance(item,list) or len(item)<=max(sp_col,he_col,pr_col): continue
            sp=str(item[sp_col]) if item[sp_col] else ""
            he=int(item[he_col]) if item[he_col] else 0
            price=float(item[pr_col]) if item[pr_col] and isinstance(item[pr_col],(int,float)) else 0
            if sp and he:
                if sp not in da_prices: da_prices[sp]={}
                da_prices[sp][he]=price
except Exception as e: print("DA error:",e)
def avg(lst): return sum(lst)/len(lst)/1000 if lst else 0
def mx(lst): return max(lst)/1000 if lst else 0
# ERCOT returns arrays - field positions: idx2=hourEnding,idx7=pan,idx11=coastal,idx15=south,idx19=west
wind_rows=wind_data.get("data",[])
def avgmw(lst): return sum(lst)/len(lst)/1000 if lst else 0
w_west=[float(r[19]) for r in wind_rows if isinstance(r,list) and len(r)>19 and r[19] and float(r[19])>0]
w_south=[float(r[15]) for r in wind_rows if isinstance(r,list) and len(r)>15 and r[15] and float(r[15])>0]
w_coastal=[float(r[11]) for r in wind_rows if isinstance(r,list) and len(r)>11 and r[11] and float(r[11])>0]
w_pan=[float(r[7]) for r in wind_rows if isinstance(r,list) and len(r)>7 and r[7] and float(r[7])>0]
wind={"west":avgmw(w_west),"south":avgmw(w_south),"coastal":avgmw(w_coastal),"pan":avgmw(w_pan)}
wind["total"]=wind["west"]+wind["south"]+wind["coastal"]+wind["pan"]
sol_rows=solar_data.get("data",[])
sv=[float(r[3]) for r in sol_rows if isinstance(r,list) and len(r)>3 and r[3] and isinstance(r[3],(int,float)) and float(r[3])>0]
wind["solar"]=max(sv)/1000 if sv else 0
print("Wind: West="+str(round(wind["west"],1))+" South="+str(round(wind["south"],1))+" Coastal="+str(round(wind["coastal"],1))+" Total="+str(round(wind["total"],1))+" Solar="+str(round(wind["solar"],1)))
load_rows=load_data.get("data",[])
load_fields=load_data.get("fields",[])
# Build field name->index map
lf_map={f.get("name","").lower():f["cardinality"]-1 for f in load_fields}
# ERCOT weather zones: coast,east,farWest,north,northCentral,south,southCentral,west,houston,systemTotal
far_west_idx=lf_map.get("farwest",lf_map.get("far west",5))
north_idx=lf_map.get("north",6)
nc_idx=lf_map.get("northcentral",lf_map.get("north central",7))
south_idx=lf_map.get("south",lf_map.get("southcentral",8))
houston_idx=lf_map.get("houston",lf_map.get("coast",3))
total_idx=lf_map.get("systemtotal",lf_map.get("system total",11))
west_vals=[]
south_vals=[]
north_vals=[]
houston_vals=[]
total_vals=[]
for r in load_rows:
    if not isinstance(r,list) or len(r)<12: continue
    def gv(idx): return float(r[idx]) if idx<len(r) and r[idx] and isinstance(r[idx],(int,float)) and float(r[idx])>0 else 0
    west_vals.append(gv(far_west_idx))
    south_vals.append(gv(south_idx))
    north_vals.append(gv(north_idx)+gv(nc_idx))
    houston_vals.append(gv(houston_idx))
    total_vals.append(gv(total_idx))
def mxmw(lst): return max(lst)/1000 if lst else 0
load={"west":mxmw(west_vals),"south":mxmw(south_vals),"north":mxmw(north_vals),"houston":mxmw(houston_vals)}
load["total"]=mxmw(total_vals)
print("Load: West="+str(round(load["west"],1))+" South="+str(round(load["south"],1))+" North="+str(round(load["north"],1))+" Houston="+str(round(load["houston"],1))+" Total="+str(round(load["total"],1)))
si=shadow_data.get("_embedded",{}).get("dam_shadow_prices",shadow_data.get("data",[]))
sc={}
for r in si:
    if not isinstance(r,dict): continue
    nm=r.get("constraintName") or r.get("name") or "Unknown"
    sp=abs(float(r.get("shadowPrice") or 0))
    he=int(r.get("deliveryHour") or 0)
    if nm not in sc: sc[nm]={"sps":[],"hrs":[]}
    if sp>0.01: sc[nm]["sps"].append(sp); sc[nm]["hrs"].append(he)
shadow_list=sorted([{"name":k,"maxSP":max(v["sps"]),"hours":sorted(set(v["hrs"])),"cnt":len(v["sps"])} for k,v in sc.items() if v["sps"]],key=lambda x:-x["maxSP"])[:20]
hub_prices={zone:da_prices.get(hub_sp,{}) for zone,hub_sp in ZONE_HUBS.items()}
site_spreads={}
SOLAR_HE=set(range(9,15))
for sp,zone in SITE_ZONES.items():
    shp=da_prices.get(sp,{})
    zhp=hub_prices.get(zone,{})
    if not shp or not zhp: continue
    outliers=[]
    for he in range(1,25):
        sp_=shp.get(he)
        hp=zhp.get(he)
        if sp_ is None or hp is None: continue
        spread=sp_-hp
        thresh=8.0 if he in SOLAR_HE else 10.0
        if abs(spread)>=thresh: outliers.append({"he":he,"spread":round(spread,2),"sp":round(sp_,2),"hp":round(hp,2)})
    if outliers: site_spreads[sp]={"zone":zone,"outliers":outliers,"name":SITE_NAMES.get(sp,sp)}
constraint_signals={}
for sp,spread_info in site_spreads.items():
    for sf_site,settlement in SF_TO_SP.items():
        if settlement!=sp: continue
        for cname,cdata in SF_DATA.items():
            sf_val=cdata["sf"].get(sf_site,0)
            if abs(sf_val)<0.05: continue
            avg_spread=sum(o["spread"] for o in spread_info["outliers"])/len(spread_info["outliers"])
            if (sf_val>0 and avg_spread>0) or (sf_val<0 and avg_spread<0):
                if cname not in constraint_signals: constraint_signals[cname]={"sites":[],"peak_he":cdata["peak_he"],"total":cdata["total"]}
                constraint_signals[cname]["sites"].append({"name":spread_info["name"],"sf":sf_val,"spread":round(avg_spread,2)})
sf_lines=[name[:42]+" PeakHE:"+str(cdata["peak_he"])+" "+str({k:round(v,3) for k,v in cdata["sf"].items() if abs(v)>=0.05}) for name,cdata in sorted(SF_DATA.items(),key=lambda x:-x[1]["total"])[:25] if any(abs(v)>=0.05 for v in cdata["sf"].values())]
SF_TEXT=chr(10).join(sf_lines)
shadow_text=""
if shadow_list: shadow_text="ERCOT DAM BINDING:"+chr(10)+chr(10).join(["  "+c["name"][:42]+": $"+str(int(c["maxSP"]))+"/MWh HE"+",".join(map(str,c["hours"][:3])) for c in shadow_list[:10]])
spread_text=""
if site_spreads:
    spread_text="HEN DA OUTLIERS:"+chr(10)
    for sp,info in sorted(site_spreads.items(),key=lambda x:-max(abs(o["spread"]) for o in x[1]["outliers"]))[:8]:
        hs=",".join(["HE"+str(o["he"])+"($"+str(o["spread"])+")" for o in sorted(info["outliers"],key=lambda x:abs(x["spread"]),reverse=True)[:3]])
        spread_text+="  "+info["name"]+"("+info["zone"]+"): "+hs+chr(10)
da_sig_text=""
if constraint_signals:
    da_sig_text="DA CONSTRAINT SIGNALS:"+chr(10)
    for c,info in sorted(constraint_signals.items(),key=lambda x:-x[1]["total"])[:6]:
        st=",".join([s["name"] for s in info["sites"][:3]])
        da_sig_text+="  "+c[:40]+": "+st+chr(10)
user_msg="HEN Bid Briefing "+TODAY+" ("+SEASON+") run "+NOW.strftime("%H:%M CDT")+chr(10)
user_msg+="ERCOT: Wind West:"+str(round(wind["west"],1))+"GW South:"+str(round(wind["south"],1))+"GW Coastal:"+str(round(wind["coastal"],1))+"GW Total:"+str(round(wind["total"],1))+"GW Solar:"+str(round(wind["solar"],1))+"GW"+chr(10)
user_msg+="Load West:"+str(round(load["west"],1))+"GW South:"+str(round(load["south"],1))+"GW North:"+str(round(load["north"],1))+"GW Houston:"+str(round(load["houston"],1))+"GW"+chr(10)+chr(10)
user_msg+=shadow_text+chr(10)+spread_text+chr(10)+da_sig_text+chr(10)
user_msg+="Bid window HE17 today through HE16 tomorrow. For each constraint identify whether HEN sites face discharge risk (positive SF) or charging opportunity (negative SF when LMP may go near zero or negative)."
SCHEMA="{overallRisk:HIGH/MODERATE/LOW,summary:2-3 sentences,operatorNote:key bid note,timeBlocks:{tonight:{he:HE16-24,constraints:[{name:x,risk:HIGH/MODERATE/WATCH,driver:x,henSites:[x],action:x}],summary:x},overnight:{he:HE1-7,constraints:[same structure],summary:x},morning:{he:HE8-14,constraints:[same],summary:x},afternoon:{he:HE15-24,constraints:[same],summary:x}},daSignals:{confirmedConstraints:[x],chargingOpportunity:x or none,sitesToWatch:[x]}}"
sys_msg="You are the NOC Constraint Analyst for Hunt Energy Network (HEN) preparing daily bids."+chr(10)
sys_msg+="HEN has 32 battery sites in ERCOT West, South, North, Houston zones."+chr(10)
sys_msg+="Bid window is HE17 today through HE16 tomorrow. HE1=midnight-1am HE8=7am-8am HE17=4pm-5pm HE24=11pm-midnight."+chr(10)
sys_msg+="TIME BLOCKS: TONIGHT=HE17-24 today, OVERNIGHT=HE1-7 tomorrow, MORNING=HE8-14 tomorrow, AFTERNOON=HE15-16 tomorrow."+chr(10)+chr(10)
sys_msg+="HEN SHIFT FACTOR DATA:"+chr(10)+SF_TEXT+chr(10)+chr(10)
sys_msg+="CRITICAL SHIFT FACTOR RULES:"+chr(10)
sys_msg+="Positive SF site = on LOAD side. Constraint binding pushes LMP HIGHER than hub. Discharging earns congestion premium."+chr(10)
sys_msg+="Negative SF site = on GENERATION side. Constraint binding pushes LMP toward ZERO or NEGATIVE. This is a CHARGING OPPORTUNITY."+chr(10)
sys_msg+="Example: WESTEX constraint with Judkins SF=-0.71 means when WESTEX binds during high renewables, Judkins LMP goes near zero or negative. Flag as charging opportunity not risk."+chr(10)
sys_msg+="For every constraint list: positive SF sites as discharge risk, negative SF sites as charging opportunity."+chr(10)
sys_msg+="RULES: ASCII only. No apostrophes. No em-dashes. No newlines in strings."+chr(10)
sys_msg+="Return ONLY valid JSON matching: "+SCHEMA
print("Calling Claude...")
cr=requests.post("https://api.anthropic.com/v1/messages",headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-6","max_tokens":2000,"system":sys_msg,"messages":[{"role":"user","content":user_msg}]},timeout=90)
raw=cr.json()["content"][0]["text"]
clean=re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"," ",raw)
clean=re.sub(r"\r\n|\r|\n"," ",clean)
chunk=clean[clean.index("{"):clean.rindex("}")+1]
try:
    result=json.loads(chunk)
except json.JSONDecodeError as je:
    print("JSON parse failed at char "+str(je.pos)+", using repair...")
    cr2=requests.post("https://api.anthropic.com/v1/messages",headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01"},json={"model":"claude-sonnet-4-6","max_tokens":2000,"system":"Fix broken JSON. Return ONLY valid JSON. No explanation.","messages":[{"role":"user","content":"Fix: "+chunk[:4000]}]},timeout=60)
    raw2=cr2.json()["content"][0]["text"]
    clean2=re.sub(r"[\x00-\x1f\x7f]"," ",raw2)
    clean2=re.sub(r"\r\n|\r|\n"," ",clean2)
    result=json.loads(clean2[clean2.index("{"):clean2.rindex("}")+1])
overall_risk=result.get("overallRisk","MODERATE")
summary=result.get("summary","")
op_note=result.get("operatorNote","")
time_blocks=result.get("timeBlocks",{})
da_signals=result.get("daSignals",{})
rc="#c0392b" if overall_risk=="HIGH" else "#9a6200" if overall_risk=="MODERATE" else "#1d6b3e"
Q=chr(39)
def risk_color(r): return "#c0392b" if r=="HIGH" else "#9a6200" if r=="MODERATE" else "#4BACC6"
def risk_bg(r): return "rgba(224,82,82,0.12)" if r=="HIGH" else "rgba(212,135,42,0.1)" if r=="MODERATE" else "rgba(75,172,198,0.08)"
def constraint_card(c):
    r=c.get("risk","MODERATE")
    col=risk_color(r)
    bg=risk_bg(r)
    sites=c.get("henSites",[])
    sites_html="".join(["<span style="+Q+"display:inline-block;font-size:10px;padding:2px 7px;border-radius:3px;background:rgba(75,172,198,0.15);color:#4BACC6;margin-right:4px;margin-bottom:3px;font-family:monospace"+Q+">"+s+"</span>" for s in sites])
    action=c.get("action","")
    out="<div style="+Q+"background:"+bg+";border-left:3px solid "+col+";border-radius:0 6px 6px 0;padding:11px 14px;margin-bottom:8px"+Q+">"
    out+="<div style="+Q+"display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px"+Q+">"
    out+="<strong style="+Q+"font-size:13px;color:#e8f4f8"+Q+">"+c.get("name","")+"</strong>"
    out+="<span style="+Q+"font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;background:"+col+";color:white"+Q+">"+r+"</span></div>"
    out+="<div style="+Q+"font-size:12px;color:#a0b8c8;margin-bottom:6px"+Q+">"+c.get("driver","")+"</div>"
    if sites: out+="<div style="+Q+"margin-bottom:5px"+Q+">"+sites_html+"</div>"
    if action: out+="<div style="+Q+"font-size:11px;color:#c8b87a;padding:5px 8px;background:rgba(212,135,42,0.08);border-radius:3px"+Q+"><strong>Bid note:</strong> "+action+"</div>"
    out+="</div>"
    return out
def block_section(bname,bdata):
    if not bdata: return ""
    constraints=bdata.get("constraints",[])
    blk_sum=bdata.get("summary","")
    he_range=bdata.get("he","")
    if not constraints: return ""
    cards="".join([constraint_card(c) for c in constraints])
    out="<div style="+Q+"background:#0d1825;border:0.5px solid rgba(75,172,198,0.15);border-radius:10px;padding:1.25rem;margin-bottom:1rem"+Q+">"
    out+="<div style="+Q+"display:flex;align-items:center;gap:10px;margin-bottom:10px"+Q+">"
    out+="<div style="+Q+"width:3px;height:16px;background:#4BACC6;border-radius:2px;flex-shrink:0"+Q+"></div>"
    out+="<div><div style="+Q+"font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6"+Q+">"+bname+"</div>"
    out+="<div style="+Q+"font-size:10px;color:#3d6478;font-family:monospace"+Q+">"+he_range+"</div></div></div>"
    if blk_sum: out+="<div style="+Q+"font-size:12px;color:#7ea8bc;margin-bottom:12px;line-height:1.5"+Q+">"+blk_sum+"</div>"
    out+=cards+"</div>"
    return out
def gcell(label,val,warn=False,alert=False):
    col="#c0392b" if alert else "#9a6200" if warn else "#e8f4f8"
    bg="rgba(224,82,82,0.07)" if alert else "rgba(212,135,42,0.07)" if warn else "#111f30"
    return "<div style="+Q+"background:"+bg+";border-radius:6px;padding:10px 12px"+Q+"><div style="+Q+"font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#3d6478;margin-bottom:4px"+Q+">"+label+"</div><div style="+Q+"font-size:20px;font-weight:600;color:"+col+";font-family:monospace"+Q+">"+val+"</div></div>"
body=""
body+="<div style="+Q+"background:rgba("+("224,82,82" if overall_risk=="HIGH" else "212,135,42" if overall_risk=="MODERATE" else "61,186,122")+",0.08);border:1px solid "+rc+";border-radius:10px;padding:16px 20px;margin-bottom:1rem"+Q+">"
body+="<div style="+Q+"display:flex;justify-content:space-between;align-items:flex-start"+Q+">"
body+="<div><div style="+Q+"font-size:11px;color:#3d6478;font-family:monospace;margin-bottom:4px"+Q+">"+TODAY+" - Bid window HE16 today to HE24 tomorrow</div>"
body+="<div style="+Q+"font-size:13px;color:#e8f4f8;line-height:1.55"+Q+">"+summary+"</div></div>"
body+="<span style="+Q+"font-size:11px;font-weight:700;padding:4px 12px;border-radius:4px;background:"+rc+";color:white;flex-shrink:0;margin-left:12px"+Q+">"+overall_risk+"</span></div>"
if op_note: body+="<div style="+Q+"margin-top:10px;font-size:12px;color:#c8b87a;padding:8px 12px;background:rgba(212,135,42,0.08);border-left:3px solid #9a6200;border-radius:0 4px 4px 0"+Q+"><strong>Bid note:</strong> "+op_note+"</div>"
body+="</div>"
body+="<div style="+Q+"background:#0d1825;border:0.5px solid rgba(75,172,198,0.12);border-radius:10px;padding:1rem;margin-bottom:1rem"+Q+">"
body+="<div style="+Q+"display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:8px"+Q+">"
body+=gcell("West wind",str(round(wind["west"],1))+" GW",wind["west"]<5,wind["west"]<2)
body+=gcell("South wind",str(round(wind["south"],1))+" GW",wind["south"]>1.5,wind["south"]>2.5)
body+=gcell("Coastal",str(round(wind["coastal"],1))+" GW",wind["coastal"]>1.5,wind["coastal"]>2.5)
body+=gcell("Total wind",str(round(wind["total"],1))+" GW",wind["total"]<5 or wind["total"]>12,wind["total"]<2)
body+=gcell("Solar",str(round(wind["solar"],1))+" GW")
body+=gcell("Season",SEASON)
body+="</div><div style="+Q+"display:grid;grid-template-columns:repeat(6,1fr);gap:8px"+Q+">"
body+=gcell("West load",str(round(load["west"],1))+" GW",load["west"]>=8.5,load["west"]>=9.5)
body+=gcell("South load",str(round(load["south"],1))+" GW",load["south"]>=16,load["south"]>=18)
body+=gcell("North load",str(round(load["north"],1))+" GW",load["north"]>=20,load["north"]>=22)
body+=gcell("Houston load",str(round(load["houston"],1))+" GW",load["houston"]>=16,load["houston"]>=18)
body+=gcell("ERCOT total",str(round(load["total"],1))+" GW")
body+=gcell("Updated",NOW.strftime("%H:%M CDT"))
body+="</div></div>"
if site_spreads:
    rows=""
    for sp,info in sorted(site_spreads.items(),key=lambda x:-max(abs(o["spread"]) for o in x[1]["outliers"]))[:12]:
        ms=max(info["outliers"],key=lambda x:abs(x["spread"]))
        col="#f28b82" if ms["spread"]>0 else "#5db87a"
        sign="+" if ms["spread"]>0 else ""
        rows+="<tr><td style="+Q+"padding:5px 8px;font-size:11px;color:#e8f4f8;border-bottom:1px solid rgba(255,255,255,0.04)"+Q+">"+info["name"]+"</td><td style="+Q+"padding:5px 8px;font-size:10px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.04)"+Q+">"+info["zone"]+"</td><td style="+Q+"padding:5px 8px;font-size:12px;font-weight:600;color:"+col+";border-bottom:1px solid rgba(255,255,255,0.04)"+Q+">"+sign+str(ms["spread"])+"</td><td style="+Q+"padding:5px 8px;font-size:10px;color:#7ea8bc;border-bottom:1px solid rgba(255,255,255,0.04)"+Q+">HE"+str(ms["he"])+"</td></tr>"
    body+="<div style="+Q+"background:#0d1825;border:0.5px solid rgba(75,172,198,0.15);border-radius:10px;padding:1.25rem;margin-bottom:1rem"+Q+">"
    body+="<div style="+Q+"display:flex;align-items:center;gap:10px;margin-bottom:10px"+Q+"><div style="+Q+"width:3px;height:16px;background:#4BACC6;border-radius:2px"+Q+"></div><div style="+Q+"font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#4BACC6"+Q+">DA Price Signals</div></div>"
    body+="<table style="+Q+"width:100%;border-collapse:collapse"+Q+"><thead><tr><th style="+Q+"text-align:left;font-size:9px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"+Q+">Site</th><th style="+Q+"text-align:left;font-size:9px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"+Q+">Zone</th><th style="+Q+"text-align:left;font-size:9px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"+Q+">Spread vs Hub</th><th style="+Q+"text-align:left;font-size:9px;color:#3d6478;padding:0 8px 6px;border-bottom:1px solid rgba(255,255,255,0.06)"+Q+">Peak HE</th></tr></thead><tbody>"+rows+"</tbody></table>"
    confirmed=da_signals.get("confirmedConstraints",[])
    charging=da_signals.get("chargingOpportunity","none")
    watching=da_signals.get("sitesToWatch",[])
    if confirmed: body+="<div style="+Q+"font-size:11px;color:#5db87a;margin-top:10px"+Q+">DA confirmed: "+", ".join(confirmed)+"</div>"
    if charging and charging!="none": body+="<div style="+Q+"font-size:12px;color:#c8b87a;padding:8px 12px;background:rgba(212,135,42,0.08);border-left:3px solid #9a6200;border-radius:0 4px 4px 0;margin-top:10px"+Q+"><strong>Charging opportunity:</strong> "+charging+"</div>"
    if watching: body+="<div style="+Q+"font-size:11px;color:#7ea8bc;margin-top:8px"+Q+">Sites to watch: "+", ".join(watching)+"</div>"
    body+="</div>"
body+=block_section("Tonight HE17-24 (4PM-Midnight)",time_blocks.get("tonight",{}))
body+=block_section("Overnight HE1-7 (Midnight-6AM)",time_blocks.get("overnight",{}))
body+=block_section("Morning / Solar HE8-14 (7AM-1PM)",time_blocks.get("morning",{}))
body+=block_section("Afternoon HE15-16 (2PM-3PM)",time_blocks.get("afternoon",{}))
html="<!DOCTYPE html><html lang="+Q+"en"+Q+"><head><meta charset="+Q+"UTF-8"+Q+"><meta name="+Q+"viewport"+Q+" content="+Q+"width=device-width,initial-scale=1.0"+Q+">"
html+="<title>HEN Bid Briefing "+TODAY+"</title>"
html+="<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#070f1a;color:#e8f4f8;min-height:100vh}</style></head><body>"
html+="<div style="+Q+"background:#022a4e;border-bottom:1px solid rgba(75,172,198,0.25);padding:0 1.5rem;height:52px;display:flex;align-items:center;justify-content:space-between"+Q+">"
html+="<div style="+Q+"display:flex;align-items:center;gap:10px"+Q+"><svg fill="+Q+"#4BACC6"+Q+" width="+Q+"20"+Q+" height="+Q+"20"+Q+" viewBox="+Q+"0 0 24 24"+Q+"><path d="+Q+"M13 2L3 14h9l-1 8 10-12h-9l1-8z"+Q+"/></svg><strong style="+Q+"font-size:14px"+Q+">HEN Congestion Dashboard</strong></div>"
html+="<div style="+Q+"display:flex;align-items:center;gap:8px"+Q+"><span style="+Q+"font-size:11px;color:#4BACC6;background:rgba(75,172,198,0.1);border:1px solid rgba(75,172,198,0.25);padding:3px 10px;border-radius:4px;font-family:monospace"+Q+">"+TODAY+" Bid Prep</span>"
html+="<span style="+Q+"font-size:10px;font-weight:700;padding:3px 9px;border-radius:4px;background:"+rc+";color:white"+Q+">"+overall_risk+"</span></div></div>"
html+="<div style="+Q+"max-width:960px;margin:0 auto;padding:1.5rem"+Q+">"+body+"</div></body></html>"
with open("results.html","w") as f: f.write(html)
print("Done. Risk:"+overall_risk+" DA_spreads:"+str(len(site_spreads))+" Blocks:"+str(len(time_blocks)))
