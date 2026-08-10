"""Built-in official career source identities for the initial China pilot."""

from __future__ import annotations

from typing import Any, Dict, Tuple


OFFICIAL_CAREER_SOURCES_CN: Tuple[Dict[str, Any], ...] = (
    {
        "source_id": "src_cn_tencent",
        "company_name": "腾讯",
        "official_domain": "hr.tencent.com",
        "source_url": "https://hr.tencent.com/zh-cn/",
        "delegated_domains": ["careers.tencent.com", "zhaopin.tencent.com"],
        "source_type": "company_careers",
        "refresh_policy": "disabled",
        "automation_allowed": False,
        "policy_url": "https://careers.tencent.com/m/zh-cn/termsservice.html",
    },
    {
        "source_id": "src_cn_huawei",
        "company_name": "华为",
        "official_domain": "career.huawei.com",
        "source_url": "https://career.huawei.com/cn/social-recruitment",
        "source_type": "company_careers",
        "refresh_policy": "disabled",
        "automation_allowed": False,
    },
    {
        "source_id": "src_cn_bytedance",
        "company_name": "字节跳动",
        "official_domain": "jobs.bytedance.com",
        "source_url": "https://jobs.bytedance.com/",
        "source_type": "company_careers",
        "refresh_policy": "disabled",
        "automation_allowed": False,
    },
    {
        "source_id": "src_cn_meituan",
        "company_name": "美团",
        "official_domain": "zhaopin.meituan.com",
        "source_url": "https://zhaopin.meituan.com/web/social",
        "source_type": "company_careers",
        "refresh_policy": "disabled",
        "automation_allowed": False,
    },
    {
        "source_id": "src_cn_baidu",
        "company_name": "百度",
        "official_domain": "talent.baidu.com",
        "source_url": "https://talent.baidu.com/jobs/social",
        "source_type": "company_careers",
        "refresh_policy": "disabled",
        "automation_allowed": False,
    },
)
