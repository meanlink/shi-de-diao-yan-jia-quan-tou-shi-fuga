"""共享计算的内容指纹与规则版本工具。

合用条件（三项完全一致才合用一次计算）：
1. 样本内容：逐行规范化为 (day, team, zone, observed, passed, frame_size) 元组后排序，
   行序不同得到相同指纹；
2. 参数：按参数键排序的规范化字典；
3. 计算规则版本：指纹口径版本 + 分析算法契约版本。
"""
import hashlib
import json

from src.constants import rules

_ROW_KEYS = ('day', 'team', 'zone', 'observed', 'passed', 'frame_size')


def _scalar(value):
    # 数值统一走十进制字符串，避免 1 与 1.0、浮点尾差造成误判
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _trim_float(value)
    return str(value).strip()


def _trim_float(value):
    text = repr(float(value))
    if text.endswith('.0'):
        return text[:-2]
    return text


def canonical_row(record):
    return tuple(_scalar(record.get(key)) for key in _ROW_KEYS)


def sample_fingerprint(records):
    """行序无关的样本内容指纹。"""
    rows = sorted(canonical_row(r) for r in records)
    payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f'{rules.SAMPLE_FINGERPRINT_VERSION}:{digest}'


def params_fingerprint(params):
    normalized = {key: _scalar(value) for key, value in sorted(params.items())}
    payload = json.dumps(normalized, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def share_key(records, params):
    """共享计算唯一键：样本内容 + 参数 + 计算规则版本。"""
    return '|'.join((
        sample_fingerprint(records),
        params_fingerprint(params),
        rules.CALC_RULE_VERSION,
    ))
