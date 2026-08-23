# Naruto Video Labeler

离线录像复盘与标注工具，面向《火影忍者手游》的练习录像和赛后分析。

- 直接在网页中播放六段已授权样本，并审核候选片段；
- 将摇杆、按钮、受击/伤害闪光、血条和蓝/红环位置作为**待审核视觉信号**；
- 不连接游戏客户端，不生成或发送游戏控制。

## 在线标注页

[打开标注页](https://xxsxjt.github.io/naruto-video-labeler/)

## 分析器源码

Python 离线分析器在 [analyzer/](analyzer/)：

~~~bash
cd analyzer
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m naruto_video_analyzer analyze input.mp4 --output report.json
~~~

新版报告会将相邻画面变化去抖合并为一个连续候选片段，并保留起止时间、持续时长和观察次数。位置环按频率限制记录，避免特效抖动产生大量冗余条目。

## 数据边界

只把项目所有者提供或创作者明确授权的录像用于训练与评估。公开教程和赛事视频仅作为规则与战术参考，除非获得额外授权。