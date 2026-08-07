"""Build the curated retrieval challenge set.

The labels are a review draft produced alongside the knowledge base.  Set
``annotation_status`` to ``human_verified`` only after a person has checked the
query, source passage and boundary cases one by one.
"""

from __future__ import annotations

import json
from pathlib import Path


OUTPUT = Path("data/eval/retrieval_qa.json")


# source, chunk index, query, difficulty, query type
POSITIVE_CASES = [
    ("account_security.md", 0, "除了微信登录，账号还能绑定哪些找回方式？", "medium", "paraphrase"),
    ("account_security.md", 1, "改完密码后，之前登录的手机还会保持在线吗？", "hard", "boundary"),
    ("account_security.md", 2, "原手机号和邮箱都收不到验证码，人工找回一般审几天？", "hard", "numeric"),
    ("account_security.md", 3, "平台自己会不会留着我的完整银行卡号？", "medium", "paraphrase"),
    ("account_security.md", 5, "旧号码停用了，换绑手机需要交什么材料？", "hard", "boundary"),
    ("account_security.md", 7, "注销后页面多久看不到个人资料，交易记录也一起删吗？", "hard", "boundary"),
    ("account_security.md", 8, "注销账号后积分和发票记录分别会怎么处理？", "hard", "cross_topic"),
    ("invoice_policy.md", 0, "企业开专票除了名称税号还要准备什么？", "hard", "list"),
    ("invoice_policy.md", 1, "专票资质过了以后，和电子普票哪个开得更快？", "hard", "comparison"),
    ("invoice_policy.md", 2, "原价500，用券和积分后付了380，票面按哪个数？", "hard", "scenario"),
    ("invoice_policy.md", 4, "收货后第25天才想起来开票，还能要纸质的吗？", "hard", "boundary"),
    ("invoice_policy.md", 6, "票已经开出来才发现抬头写错，自己在订单页能改吗？", "hard", "boundary"),
    ("invoice_policy.md", 8, "只退订单里的一件商品，原发票必须作废重开吗？", "hard", "boundary"),
    ("invoice_policy.md", 9, "发票作废成功是不是就代表退款已经进银行卡了？", "hard", "negative_premise"),
    ("membership_policy.md", 0, "会员级别看累计消费多久的记录，又在哪天重算？", "hard", "multi_fact"),
    ("membership_policy.md", 1, "年消费八千和两万五分别是什么等级、几倍积分？", "hard", "comparison"),
    ("membership_policy.md", 2, "等级到期降了，之前攒的分会跟着清空吗？", "hard", "negative_premise"),
    ("membership_policy.md", 3, "评价带视频每单能拿几分，可以反复评价刷吗？", "hard", "boundary"),
    ("membership_policy.md", 4, "三千积分最多抵多少，一笔订单还有比例上限吗？", "hard", "calculation"),
    ("membership_policy.md", 6, "昨晚消费已经够升级，今天为什么等级还没变？", "hard", "scenario"),
    ("membership_policy.md", 8, "退款完成后，消费额和积分什么时候影响等级？", "hard", "cross_topic"),
    ("membership_policy.md", 9, "积分抵扣为什么既影响会员累计消费又影响发票金额？", "hard", "cross_topic"),
    ("promotion_policy.md", 0, "哪一种券不要求凑门槛，哪一种只能买指定类目？", "medium", "comparison"),
    ("promotion_policy.md", 1, "满减券、无门槛券和秒杀活动能不能一起叠？", "hard", "constraint"),
    ("promotion_policy.md", 2, "平时一单620元按日常档位减多少，能跨店凑吗？", "hard", "calculation"),
    ("promotion_policy.md", 4, "金额明明够了券仍是灰色，除了过期还有哪些可能？", "hard", "list"),
    ("promotion_policy.md", 6, "双十一下单后第二天更便宜，平台会补差额吗？", "medium", "scenario"),
    ("promotion_policy.md", 8, "补偿发的无门槛券可以转到家人的账号吗？", "hard", "boundary"),
    ("promotion_policy.md", 10, "部分退款和整单退款时，用掉的券是否都会返还？", "hard", "comparison"),
    ("promotion_policy.md", 11, "活动页写满99包邮，寄西藏是否一定不用运费？", "hard", "cross_topic"),
    ("refund_policy.md", 0, "第七天晚上提交普通商品无理由退货还在期限内吗？", "hard", "boundary"),
    ("refund_policy.md", 1, "商品没坏但盒子、配件和票据缺了，能按无理由退吗？", "hard", "constraint"),
    ("refund_policy.md", 2, "仓库验收通过后第三天还没收到原路退款正常吗？", "medium", "numeric"),
    ("refund_policy.md", 3, "生鲜、定制、虚拟商品都能套用七天无理由吗？", "hard", "negative_premise"),
    ("refund_policy.md", 4, "确认为非人为质量故障后，只能退款不能修或换吗？", "hard", "negative_premise"),
    ("refund_policy.md", 5, "用积分下单又开了发票，退款前后要分别看哪些规则？", "hard", "cross_topic"),
    ("shipping_policy.md", 0, "现货遇到双十一时，48小时承诺可能延到多久？", "hard", "boundary"),
    ("shipping_policy.md", 1, "订单88元寄内蒙古，一定只收普通地区运费吗？", "hard", "scenario"),
    ("shipping_policy.md", 2, "正常情况下同城和西部跨省预计分别几天？", "medium", "comparison"),
    ("shipping_policy.md", 3, "暴雪期间超出表格里的配送天数就一定算平台违约吗？", "hard", "negative_premise"),
    ("shipping_policy.md", 5, "显示揽收后一天没轨迹该等还是催，超过多久再联系？", "hard", "boundary"),
    ("shipping_policy.md", 7, "签收后第二天才发现运输破损，还能按24小时规则报吗？", "hard", "boundary"),
    ("shipping_policy.md", 9, "包裹已经出库，能让平台直接把地址改到另一个省吗？", "hard", "boundary"),
    ("shipping_policy.md", 11, "我愿意补运费，结算时可以指定顺丰吗？", "medium", "negative_premise"),
    ("shipping_policy.md", 12, "物流破损核实后，是物流规则直接决定退款到账时间吗？", "hard", "cross_topic"),
    ("troubleshooting_faq.md", 1, "耳机有电但手机搜不到，旧配对记录和充电盒该怎么处理？", "hard", "procedure"),
    ("troubleshooting_faq.md", 3, "一只耳机没声时，怎么区分没电、手机声道设置和硬件故障？", "hard", "diagnosis"),
    ("troubleshooting_faq.md", 5, "耳机在人多的地方断续，是先送修还是先排除信号和固件？", "hard", "diagnosis"),
    ("troubleshooting_faq.md", 7, "使用一年续航掉18%和短期掉35%，哪个更可能走售后？", "hard", "comparison"),
    ("troubleshooting_faq.md", 9, "无线键盘几个键失灵，除了清异物还应检查接口和什么？", "hard", "procedure"),
    ("troubleshooting_faq.md", 11, "驱动软件认不到键盘，重装之前还能做哪些连接排查？", "hard", "procedure"),
    ("troubleshooting_faq.md", 13, "键盘完全无反应，线、接收器和设备管理器分别怎么查？", "hard", "procedure"),
    ("troubleshooting_faq.md", 15, "键盘进液后为什么不能马上通电或用热风吹？", "hard", "procedure"),
    ("troubleshooting_faq.md", 16, "排查手册说可能硬件坏了，就一定能免费换新吗？", "hard", "cross_topic"),
    ("warranty_policy.md", 0, "耳机、键盘、线材和显示器四类产品各保多久？", "hard", "list"),
    ("warranty_policy.md", 1, "保修从付款、发货还是签收那天起算，以什么记录为准？", "hard", "boundary"),
    ("warranty_policy.md", 2, "免费保修的核心条件是故障发生在期限内还是还要非人为？", "hard", "constraint"),
    ("warranty_policy.md", 3, "单边无声和外壳开裂都可能保修，但要满足什么原因条件？", "hard", "constraint"),
    ("warranty_policy.md", 4, "超期、拆机和进液这几类情况是否都一定免费修？", "medium", "negative_premise"),
    ("warranty_policy.md", 5, "用非原装高压配件导致损坏，为什么不属于免费保修？", "hard", "scenario"),
    ("warranty_policy.md", 6, "寄到售后后多久修好，修不了时按什么顺序处理？", "hard", "procedure"),
    ("warranty_policy.md", 7, "收货第八天还能补买延保吗，之后可以随商品转给别人吗？", "hard", "boundary"),
    ("warranty_policy.md", 8, "物流压坏、七天退货和保修检测三个入口该怎样区分？", "hard", "cross_topic"),
    ("order_management.md", 0, "订单没付款保留多久，系统关闭后还能恢复原券和订单吗？", "hard", "boundary"),
    ("order_management.md", 1, "已经付款但仓库开始拣货了，取消按钮为什么不见了？", "hard", "scenario"),
    ("order_management.md", 2, "状态已发货还想取消，是直接退钱还是先拒收或退回？", "hard", "boundary"),
    ("order_management.md", 3, "付款后想换颜色并改用另一张券，能直接编辑订单吗？", "hard", "constraint"),
    ("order_management.md", 4, "两个订单能合成一个快递吗，一个订单为什么会有多个单号？", "hard", "comparison"),
    ("order_management.md", 5, "待发货订单能把上海地址改成杭州吗？", "hard", "boundary"),
    ("order_management.md", 6, "我已经提交订单但还没付钱，这时商品算锁库存了吗？", "hard", "negative_premise"),
    ("order_management.md", 7, "付款后盘点发现少货，部分取消时按原价还是实付退款？", "hard", "scenario"),
    ("order_management.md", 8, "预售和现货一起买，默认会先发现货还是等齐？", "medium", "boundary"),
    ("order_management.md", 9, "我从订单列表删除记录，平台保存的交易资料也会被删吗？", "hard", "negative_premise"),
    ("payment_policy.md", 0, "结算页除了微信支付宝还支持什么，能货到付款吗？", "medium", "list"),
    ("payment_policy.md", 1, "余额不够时能否一半微信一半支付宝补齐？", "hard", "constraint"),
    ("payment_policy.md", 2, "银行卡扣了钱订单仍待付款，多久内别重复付，何时提交凭证？", "hard", "boundary"),
    ("payment_policy.md", 3, "没扣款的支付失败可能和限额有关，平台能帮我调银行限额吗？", "hard", "negative_premise"),
    ("payment_policy.md", 4, "同一笔付款被扣两次，核实后多出来的钱多久退？", "medium", "numeric"),
    ("payment_policy.md", 5, "平台显示退款完成两天了银行卡没到，和微信到账速度一样吗？", "hard", "comparison"),
    ("payment_policy.md", 6, "余额加银行卡付款后退款，为什么两部分不是同时到账？", "hard", "scenario"),
    ("payment_policy.md", 7, "原银行卡注销了，能要求平台把退款改到家人的卡吗？", "hard", "boundary"),
    ("payment_policy.md", 8, "分期商品退款后手续费和本期账单由平台决定吗？", "hard", "cross_topic"),
    ("payment_policy.md", 9, "客服发来退款认证链接并让我共享屏幕，应该配合吗？", "medium", "security"),
    ("exchange_policy.md", 0, "第七天想把普通商品换个颜色，包装完整就都可以换吗？", "hard", "boundary"),
    ("exchange_policy.md", 1, "客服看视频说像质量问题，这就等于售后最终认定吗？", "hard", "negative_premise"),
    ("exchange_policy.md", 2, "配件丢失又超过换货期，还能走哪一种维修规则？", "hard", "cross_topic"),
    ("exchange_policy.md", 3, "同链接换更贵和更便宜的规格，差价分别怎么处理？", "hard", "comparison"),
    ("exchange_policy.md", 4, "想换的颜色缺货，平台会先为我的申请锁住未来库存吗？", "hard", "negative_premise"),
    ("exchange_policy.md", 5, "活动结束后换同款是否重算现价，跨商品又该怎么办？", "hard", "boundary"),
    ("exchange_policy.md", 6, "检测是质量问题和个人想换颜色，两种往返运费谁承担？", "hard", "comparison"),
    ("exchange_policy.md", 7, "售后仓签收后，正常最晚多久验完并寄出替换品？", "hard", "multi_fact"),
    ("exchange_policy.md", 8, "拆箱发现少件，第3天才提交照片还符合48小时要求吗？", "hard", "boundary"),
    ("exchange_policy.md", 9, "补发还没出库和已经发出时，修改地址的规则一样吗？", "hard", "comparison"),
    ("customer_service_policy.md", 0, "晚上十一点留言，通常从什么时候开始算四小时回复？", "hard", "boundary"),
    ("customer_service_policy.md", 1, "节假日电话没人接，账号被盗有没有全天可用的紧急入口？", "hard", "boundary"),
    ("customer_service_policy.md", 2, "普通咨询、售后核查和复杂争议的处理时长分别是什么？", "hard", "comparison"),
    ("customer_service_policy.md", 3, "同一投诉连建五张工单会不会排得更靠前？", "medium", "negative_premise"),
    ("customer_service_policy.md", 4, "工单结案八天后还能在原单里申请重开吗？", "hard", "boundary"),
    ("customer_service_policy.md", 5, "改退款账户时客服会核验哪些信息，又绝不会索要什么？", "hard", "security"),
    ("customer_service_policy.md", 6, "只截一句聊天内容没有账号和时间，能作为完整争议证据吗？", "hard", "boundary"),
    ("customer_service_policy.md", 7, "申请升级复核是否保证改判，通常还要再等多久？", "hard", "negative_premise"),
    ("customer_service_policy.md", 8, "投诉快递和投诉商品故障分别必须提交哪些证据？", "hard", "comparison"),
    ("customer_service_policy.md", 9, "品牌官网买的商品可以让这个平台客服直接保修吗？", "hard", "scope"),
]


NEGATIVE_QUERIES = [
    "线下门店买的商品能在哪个柜台退货？",
    "可以用比特币或者数字人民币付款吗？",
    "你们在悉尼有没有自提仓库？",
    "家电安装师傅上门一次收费多少？",
    "商品支持刻字定制吗，刻五个字多少钱？",
    "学生认证后会员能直接升到什么等级？",
    "积分可以兑换航空里程吗？",
    "旧手机以旧换新的估价标准是什么？",
    "企业批量采购一百台键盘能打几折？",
    "发票能开美元金额和英文抬头吗？",
    "海外订单关税由平台还是收件人承担？",
    "直播间中奖的赠品保修多久？",
    "有没有宠物损坏险或者意外险？",
    "可以预约周六上午十点送到家吗？",
    "支持到店试用耳机后再决定是否购买吗？",
    "会员生日礼包具体会送哪一件商品？",
    "退款到账后银行短信一定会马上通知吗？",
]


# query, required evidence chunks, difficulty, query type
MULTI_EVIDENCE_CASES = [
    ("整单退货已经开过票，作废后钱什么时候到银行卡？", ["invoice_policy.md:8", "payment_policy.md:5"], "hard", "multi_evidence"),
    ("活动页说满99包邮，但88元寄内蒙古到底按什么规则收费？", ["promotion_policy.md:11", "shipping_policy.md:1"], "hard", "multi_evidence"),
    ("退款成功后积分被扣了，银行卡里的钱又要等多久？", ["membership_policy.md:8", "payment_policy.md:5"], "hard", "multi_evidence"),
    ("已发货订单不想要了，从取消到最终收到退款要经过哪些步骤？", ["order_management.md:2", "refund_policy.md:2"], "hard", "multi_evidence"),
    ("键盘进液想换货，换货和保修分别为什么可能要自己承担费用？", ["exchange_policy.md:2", "warranty_policy.md:5"], "hard", "multi_evidence"),
    ("键盘洒水后先怎么处理，之后还能不能免费保修？", ["troubleshooting_faq.md:15", "warranty_policy.md:5"], "hard", "multi_evidence"),
    ("注销账号并删除订单后，交易记录和个人资料会在同一时间彻底消失吗？", ["account_security.md:7", "order_management.md:9"], "hard", "multi_evidence"),
    ("原退款银行卡注销了，平台会不会因为保存过卡号而直接改退另一张卡？", ["payment_policy.md:7", "account_security.md:3"], "hard", "multi_evidence"),
    ("优惠券加积分买的商品部分退款，退款额、积分和发票金额分别受什么影响？", ["promotion_policy.md:10", "membership_policy.md:9", "invoice_policy.md:2"], "hard", "multi_evidence"),
    ("售后核查等了三天仍不满意，升级复核还要多久且一定改判吗？", ["customer_service_policy.md:2", "customer_service_policy.md:7"], "hard", "multi_evidence"),
    ("包裹既破损又少件，两个问题分别要在多久内提交哪些证据？", ["shipping_policy.md:7", "exchange_policy.md:8"], "hard", "multi_evidence"),
    ("预售和现货一起下单又赶上大促，默认何时一起发出、最长可能怎样顺延？", ["order_management.md:8", "shipping_policy.md:0"], "hard", "multi_evidence"),
    ("余额和银行卡组合付款后退款，为什么分开退而且银行卡更慢？", ["payment_policy.md:6", "payment_policy.md:5"], "hard", "multi_evidence"),
    ("商品寄到售后检测后，通常多久维修；超过普通时限要等工单多久？", ["warranty_policy.md:6", "customer_service_policy.md:2"], "hard", "multi_evidence"),
    ("积分和无门槛券能一起用吗，各自又有什么单笔使用限制？", ["promotion_policy.md:1", "membership_policy.md:4"], "hard", "multi_evidence"),
    ("换成更便宜规格产生的差额，平台用什么路径、多久退回？", ["exchange_policy.md:3", "payment_policy.md:5"], "hard", "multi_evidence"),
    ("手机邮箱都失效后申请账号找回，要交材料并等多久，工单时限又是多少？", ["account_security.md:2", "customer_service_policy.md:2"], "hard", "multi_evidence"),
    ("已开发票抬头错误，联系客服重开和一般工单首次回复各要多久？", ["invoice_policy.md:6", "customer_service_policy.md:2"], "hard", "multi_evidence"),
    ("原订单已发货和补发商品已发出，这两种情况下都还能改收货地址吗？", ["shipping_policy.md:9", "exchange_policy.md:9"], "hard", "multi_evidence"),
    ("延保买晚了又想跨商品换货，为什么两个请求都不能按原订单直接办？", ["warranty_policy.md:7", "exchange_policy.md:5"], "hard", "multi_evidence"),
]


def build() -> list[dict]:
    rows: list[dict] = []
    for index, (source, chunk_index, query, difficulty, query_type) in enumerate(
        POSITIVE_CASES, start=1
    ):
        rows.append(
            {
                "id": f"ret-pos-{index:03d}",
                "query": query,
                "answerable": True,
                "expected_source": source,
                "expected_sources": [source],
                "expected_chunk_ids": [f"{source}:{chunk_index}"],
                "match_mode": "all",
                "difficulty": difficulty,
                "query_type": query_type,
                "annotation_status": "draft_pending_human_review",
            }
        )

    for index, (query, chunk_ids, difficulty, query_type) in enumerate(
        MULTI_EVIDENCE_CASES, start=1
    ):
        sources = list(dict.fromkeys(chunk_id.rsplit(":", 1)[0] for chunk_id in chunk_ids))
        rows.append(
            {
                "id": f"ret-multi-{index:03d}",
                "query": query,
                "answerable": True,
                "expected_source": sources[0],
                "expected_sources": sources,
                "expected_chunk_ids": chunk_ids,
                "match_mode": "all",
                "difficulty": difficulty,
                "query_type": query_type,
                "annotation_status": "draft_pending_human_review",
            }
        )

    for index, query in enumerate(NEGATIVE_QUERIES, start=1):
        rows.append(
            {
                "id": f"ret-neg-{index:03d}",
                "query": query,
                "answerable": False,
                "expected_source": None,
                "expected_sources": [],
                "expected_chunk_ids": [],
                "match_mode": "all",
                "difficulty": "hard",
                "query_type": "unanswerable",
                "annotation_status": "draft_pending_human_review",
            }
        )
    return rows


if __name__ == "__main__":
    rows = build()
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {len(rows)} cases: {len(POSITIVE_CASES)} single-evidence, "
        f"{len(MULTI_EVIDENCE_CASES)} multi-evidence, {len(NEGATIVE_QUERIES)} unanswerable"
    )
