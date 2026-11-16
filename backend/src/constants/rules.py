# 计算规则版本：样本指纹口径与分析算法契约各自独立留痕。
# 任一规则改变（记录规范化、指纹算法、analyze 输出契约）都应抬升对应版本，
# 旧版本产生的共享计算不会被新版本请求复用。
SAMPLE_FINGERPRINT_VERSION = 'sfp-1'
CALC_RULE_VERSION = 'calc-1'
