# Regression scenarios

这三组 fixture 是行为契约，不是固定文案答案。回归测试检查输入、来源、事实锁、篇幅、短视频前三秒钩子、自然化状态、质量门和审核路由是否被完整声明，不要求模型每次生成相同措辞。

- `maternal-douyin.json`：验证抖音前三秒钩子和母婴健康内容的医疗条件路由。
- `ai-education-xiaohongshu.json`：验证平台内证据与网页证据不能混写。
- `fortune-wechat-video.json`：验证视频号前三秒钩子，以及命理内容的生死、疾病、收益和恐惧转化边界。

确定性的 TianAPI 字段归一化由 `test_tianapi.py` 单独测试。模型成稿质量仍需用真实请求做前向测试，不能由正则表达式证明。
