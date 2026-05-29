# TVBox 聚合源

自动聚合 TVBox 影视源，采集站测试播放速度排序，爬虫源按延迟排序，每小时自动更新。

## 使用方法

在 TVBox / 影视仓 App 中配置地址：

| 网络环境 | 配置地址 |
|---------|---------|
| 🌍 海外/通用 | `https://raw.githubusercontent.com/25175/tvyuan/master/tvbox.json` |
| 🇨🇳 国内 | `https://gitee.com/onm-hundred-and-eleven/tvyuan/raw/master/tvbox.json` |

## 说明

- 数据来源：[tvbox.clbug.com](https://tvbox.clbug.com/user.php)
- **采集站（type=0/1）**：真实测试播放速度，按播放延迟排序，名称前缀 `[播放xxxms]`
- **爬虫源（type=3）**：按源 URL 响应延迟排序，名称前缀 `[xxxms]`
- 每小时 GitHub Actions 自动更新，同步推送到 Gitee（国内镜像）
- 过滤不可用源，只保留可用的站点
