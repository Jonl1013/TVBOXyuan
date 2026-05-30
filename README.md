# TVBox 聚合源

自动聚合 TVBox 影视源，每小时 GitHub Actions 自动更新。

## 使用方法

### 📺 简洁版（推荐）

仅采集站，不依赖 JAR，**真实播放测速排序**（m3u8→分片下载），直接能用：

| 网络 | 地址 |
|------|------|
| 🇨🇳 国内 | `https://gitee.com/onm-hundred-and-eleven/tvyuan/raw/master/tvbox.json` |
| 🌍 海外 | `https://raw.githubusercontent.com/25175/tvyuan/master/tvbox.json` |

### 🗄️ 全量版

27 个源全部站点合并（246站），含采集站+爬虫站，带 spider JAR：

| 网络 | 地址 |
|------|------|
| 🇨🇳 国内 | `https://gitee.com/onm-hundred-and-eleven/tvyuan/raw/master/tvbox_full.json` |
| 🌍 海外 | `https://raw.githubusercontent.com/25175/tvyuan/master/tvbox_full.json` |

### 📦 多仓版

27 个源独立保留，每个源有自己的 JAR 和站点，可切换仓库：

| 网络 | 地址 |
|------|------|
| 🇨🇳 国内 | `https://gitee.com/onm-hundred-and-eleven/tvyuan/raw/master/tvbox_multi.json` |
| 🌍 海外 | `https://raw.githubusercontent.com/25175/tvyuan/master/tvbox_multi.json` |

## 客户端下载

| 客户端 | 多仓支持 | 下载地址 |
|--------|:-------:|---------|
| TVBox 原版 | ❌ | [GitHub 下载](https://github.com/CatVod/CatVodOpen/releases) |
| 影视仓 | ✅ | [GitHub 下载](https://github.com/q215613905/TVBox/releases) |
| OK影视 | ✅ | [GitHub 下载](https://github.com/okaapps/oktv/releases) |
| FongMi（丰米）| ✅ | [GitHub 下载](https://github.com/FongMi/CatVodOpen/releases) |

**多仓配置方式：**
- 影视仓：首页 → 配置 → 多仓地址
- OK影视：设置 → 多仓
- FongMi：设置 → 配置 → 多仓

## 说明

- 数据来源：[tvbox.clbug.com](https://tvbox.clbug.com/user.php)
- 每小时自动更新：测速 → 抓取 → 合并 → 推送
- 简洁版播放测速流程：获取视频 → 下载 m3u8 主列表 → 解析媒体列表 → 下载 ts 分片 → 计算持续速度
- 不可用源自动清洗，恢复后自动加回

## 更新频率

每小时整点（UTC `0 * * * *`），GitHub Actions 自动执行。
