# 心照笔记 · 核心维护手册

> **这份文档是给"接手的人"看的** —— 无论是人、AI、智能体还是软件。
> 本博客的很多坑**不是显而易见的**，是靠真实踩坑才定位出来的。
> 请先读完本文档，再动手。以下每一条，都对应一次真实的翻车。

最后更新：2026-10-11

---

## ★ 接手第一件事：这三条先记住

1. **分类标签不要乱加** —— 本站采用「最小起步、自然生长」原则，
   当前只有 分类 `养生`/`AI`、标签 `功法`/`健康`。
   不够用了才加，加之前先读**第五节 5.1**。
2. **图片一律放 `assets/images/`**，front matter 里路径**不带前导斜杠**（见坑 1）。
3. **改完必须先本地预览确认**，再提交推送（见第四节流程）。

---

## 一、这个站是什么

| 项目 | 说明 |
|---|---|
| 站点名 | 心照笔记 |
| 线上地址 | https://heguang259.github.io/ |
| 本地目录 | `D:/heguang259.github.io` |
| 生成器 | Hugo **extended** v0.159.1（注意必须是 extended 版） |
| 主题 | PaperMod（以 git submodule 引入） |
| 托管 | GitHub Pages |
| 部署方式 | push 到 `main` 分支后，GitHub Actions 自动构建并发布 |
| 写入方式 | 在本地改内容 → 本地预览确认 → 提交推送 |

**关键理解**：本地只负责"写"和"预览"。真正的上线动作是 `git push`。
推送成功后，`.github/workflows/hugo.yml` 会在云端重新构建，约 1–2 分钟后线上生效。

---

## 二、目录职责（必须记住）

```
D:/heguang259.github.io/
├── content/posts/          文章正文（Markdown）
├── content/categories/     分类页标题定义（_index.md）
├── content/tags/           标签页标题定义（_index.md）
├── content/404.md          404 页面标题定义
├── assets/images/          ★ 图片必须放这里（见坑 1）
├── assets/css/extended/    ★ 自己的 CSS 覆盖（见坑 2）
├── static/                 静态文件（图标等），原样拷贝不过处理
├── layouts/                ★ 覆盖主题的模板（见坑 3）
├── themes/hugo-PaperMod/   主题源码 —— 不要改！
├── hugo.toml               站点主配置
└── .github/workflows/      自动部署脚本
```

**总原则：永远不要修改 `themes/` 里的文件。**
主题是 git submodule，改它会出现：更新主题时冲突、别人拉下来看不到你的改动、
submodule 变更难以提交。要覆盖，就在项目根目录建同名文件（见坑 3）。

---

## 三、十条必知铁律（每条都是踩过的坑）

### 坑 1 · 图片必须放 `assets/`，不能放 `static/`

**现象**：图片能显示，但体积巨大、手机上加载慢，没有响应式多尺寸。

**原因**：Hugo 只对 `assets/` 里的资源做图像处理（缩放、生成 srcset）。
放 `static/` 的图片是原样拷贝，PaperMod 的封面模板会走"降级分支"，输出一个裸 `<img>`。

**正确做法**：
1. 图片放 `assets/images/xxx.jpg`
2. 文章 front matter 里这样写（**注意：路径不带开头斜杠**）：
   ```yaml
   cover:
     image: "images/calm-mind.jpg"
     alt: "对图片内容的中文描述"
   ```
   一旦写成 `"/images/xxx.jpg"`，就找不到资源，又退回降级分支了。

**怎么验证生效**：构建日志里看 `Processed images` 这一行。它为 `0` 就说明没生效。

---

### 坑 2 · 图片拉伸变形

**现象**：图片看起来被横向或纵向拉长了，比例不对。

**原因**：主题的 `reset.css` 里只有：
```css
img { display: block; max-width: 100%; }
```
**没有 `height: auto`**。当图片宽度被 `max-width` 压缩，而 HTML 上仍带着原始的
`height` 属性时，浏览器会按原高度显示 → 变形。

**修复位置**：`assets/css/extended/custom.css`（这个文件会被自动合并进最终样式）
```css
img { height: auto; }
.md-content img { height: auto; }
```
**不要**去改 `themes/hugo-PaperMod/assets/css/core/reset.css`。

---

### 坑 3 · 覆盖主题模板，要用 `layouts/` 下的同名文件

PaperMod 新版（本项目用的版本）模板路径带下划线前缀，覆盖时要注意：

| 想要改什么 | 在项目里新建这个文件 |
|---|---|
| 正文 Markdown 图片渲染 | `layouts/_markup/render-image.html` |
| 页脚注入（如脚本） | `layouts/_partials/extend_footer.html` |
| 页头注入（如 CSS/统计） | `layouts/_partials/extend_head.html` |
| 404 页 | `layouts/404.html` |

**优先级**：项目 `layouts/` > 主题 `themes/*/layouts/`。
所以只要在项目里建同名文件，就自动覆盖了，主题源码不动。

---

### 坑 4 · 首页显示全文，把页面铺满

**现象**：首页每篇文章都显示几千字全文，一直往下滑，不像"列表"。

**原因**：Hugo 的 `.Summary` 机制。
- 文章里**没有** `<!--more-->` 标记时，摘要 = 全文。
- 中文没有空格分词，`summaryLength`（按词计）对中文基本不起作用——配了也没用。

**正确做法**：在每篇文章正文的开头段落之后，单独一行插入：
```markdown
<!--more-->
```
这一行之前的内容 = 首页摘要，之后的内容 = 点进去才看到。

**注意**：`<!--more-->` 要单独占一行，前后各留一个空行。
放在小标题**之后**的话，摘要里会带上那个小标题（可以接受，但要知道）。

**怎么验证**：构建后抓 `public/index.html`，看每个条目摘要长度是不是几百字而不是几千字。

---

### 坑 5 · 分类页 / 标签页标题是英文

**现象**：点开"分类"，大标题显示 `Categories`；点开"标签"显示 `Tags`。其它菜单却是中文。

**原因**：Hugo 的 taxonomy 页面，如果没有对应的 `_index.md`，就回退到 taxonomy 的默认英文名。

**修复**：建这两个文件（本仓库已有）：
```
content/categories/_index.md   → title: "分类"
content/tags/_index.md         → title: "标签"
```
内容格式：
```yaml
---
title: "分类"
description: "按主题浏览全部文章"
---
```

---

### 坑 6 · 404 页面标题是英文

**现象**：访问不存在的地址，标题显示 `404 Page not found`。

**修复**：建 `content/404.md`（本仓库已有），关键字段：
```yaml
---
title: "页面走丢了"
url: "404.html"
layout: "404"
list: never
noindex: true
sitemap:
  disable: true
---
```
配合 `layouts/404.html` 覆盖模板，可以加上"返回首页"的引导链接。

---

### 坑 7 · 本地预览看不到响应式图片，误以为改动没生效

**现象**：本地 `hugo server` 看页面，图片还是老样子，以为白改了。

**原因**：Hugo 在 **development 模式**下**不生成** srcset（响应式多尺寸），
只有在 production 模式才处理。

**正确做法**：本地预览一定要加参数：
```bash
hugo server --baseURL http://localhost:1313/ --environment production
```
不加 `--environment production`，图片处理和 srcset 都不会出现，会误判。

---

### 坑 8 · 改了东西但线上没变 / 旧内容残留

**现象**：删了文章，首页还在；改了分类，分类页还是旧的。

**原因**：Hugo 的 `public/` 和 `resources/` 是缓存产物，有时不会自动清理旧文件。

**正确做法**：彻底重建：
```bash
rm -rf public resources
hugo --gc --minify
```
排查疑难问题时，先做这一步再看结果。

---

### 坑 9 · git 报 `your current branch appears to be broken`

**现象**：任何 git 命令都报这个错，像是仓库坏了。

**原因**：`.git/HEAD` 文件被写成了 `ref: refs/heads/.invalid`（通常是 clone 失败残留）。

**修复四步**（已验证有效）：
```bash
git fetch origin +refs/heads/main:refs/remotes/origin/main
git symbolic-ref HEAD refs/heads/main
git reset
```

---

### 坑 10 · 误判"网络不通"

**现象**：推不上去，以为网络问题。

**原因**：这台机器环境变量里配了代理 `127.0.0.1:8287`。
**`curl` 默认会读取环境变量里的代理**，所以直接用 `curl https://github.com` 测，
测的其实是代理，不是直连——结论会错。

**正确的测试方式**（强制不走代理）：
```bash
curl --noproxy '*' -I https://github.com
```

**git 的代理设置**：全局已设为空值来覆盖环境变量：
```bash
git config --global http.proxy ""
git config --global https.proxy ""
```
如果推送又出问题，先检查这两项是不是被改回去了。

**补充事实**：这台机器上 `api.github.com` 通常通，`github.com` 主站有时会被拦。
如果 git 推送超时，等网络恢复后重试即可，本地提交不会丢。

---

## 四、日常改文章的标准流程

```
1. 写 / 改   content/posts/xxx.md
2. 加摘要标记 <!--more-->（见坑 4）
3. 涉及图片 → 放 assets/images/，front matter 写不带斜杠的路径（见坑 1）
4. 本地预览：hugo server --baseURL http://localhost:1313/ --environment production
5. 浏览器确认：图片不变形、首页是摘要不是全文、标题是中文
6. 提交：git add -A && git commit -m "说明"
7. 推送：git push
8. 等 1–2 分钟，访问线上地址复查
```

---

## 五、分类与标签体系（★ 治理规范，必读）

### 5.1 核心原则：最小起步，自然生长

本博客的分类与标签**不是预先设计出来的，是长出来的**。遵循第一性原理：

1. **从最小单元起步**：只建"当下确实需要"的分类和标签，绝不为"未来可能会写"提前占位。
2. **不够用了才加**：发新文章时，如果现有分类/标签都装不下它，**才考虑新增一个**。
   一次最多加 1–2 个，不要批量铺开。
3. **不让任何人空等**：没有对应文章的分类，不要手动建，否则会出现空分类页（读者点进去是空的，体验差）。
4. **认知成本优先**：分类宜少（大众一眼看懂），标签可细（精准索引）。宁可少，不可冗余。

> 判断标准一句话：**"这一个新的，是现在就必须用，还是以后可能用？"**
> 只有"现在必须用"才加。

### 5.2 当前体系（2026-10-11 定）

**分类（2 个）**

| 分类 | 收什么内容 |
|---|---|
| `养生` | 身体健康、心理健康、功法、中医、经络、作息、身心调理等一切关于"人怎么活得更好"的内容 |
| `AI` | AI 学习笔记、工具实践、认知思考 |

**标签（2 个）**

| 标签 | 含义 |
|---|---|
| `功法` | 具体的实修方法：站桩、静坐、导引、呼吸法等 |
| `健康` | 与身体健康、调理相关的通用标记 |

**当前文章归类**

| 文章 | 分类 | 标签 |
|---|---|---|
| 站桩入门 | 养生 | 功法、健康 |
| 静坐入门 | 养生 | 功法、健康 |
| 心照笔记（站名页） | 无 | 无 |

**待生长（不预建）**：`AI` 分类目前**没有文章，因此没有对应的分类页**——这是正确的。
等第一篇 AI 文章发布时，在 front matter 写 `categories: ["AI"]`，它就会自动出现。

### 5.3 怎么加（操作方式）

**分类和标签都不需要手动建目录**，Hugo 会自动从文章的 front matter 生成页面。

在文章 front matter 里写：

```yaml
---
title: "文章标题"
categories: ["养生"]        # 通常只写 1 个分类
tags: ["功法", "健康"]      # 可以写多个标签
---
```

**规则**：
- **一篇文章只归一个分类**（主流做法，避免分类失去聚合意义）
- **标签可以有多个**（标签是"多入口"，让人从不同角度找到这篇文章）
- 中文直接写，不需要引号以外的东西；分类/标签名**一旦定下就不要改名**（改名等于换了一个新分类，旧链接会失效）

### 5.4 关于命名的一个原则：门要低，内核在屋里

**分类名 = 门面**，出现在导航栏，人人可见 → 用**最通俗、最不吓人**的词。
**标签名 = 索引**，主动搜索的人才看到 → 可以放**更精准、更有内核**的词。

举例：站桩、静坐这类内容，分类用 `养生`（大众都懂、无门槛），标签用 `功法`（指向实修内核）。
**不要把"修行""玄学"这类词放进分类**——它会把只想了解养生的普通读者挡在门外。
内容里的深度（道家、心性、内观）通过**文章正文**去讲，不靠分类标签承载。

---

## 五之二、新增其他章节页面

- 文章类内容统一放 `content/posts/`
- 独立页面（关于、归档、搜索等）放 `content/` 根目录
- 新增独立页面后，如需出现在顶部菜单，要在 `hugo.toml` 的 `[[menu.main]]` 里加一条

---

## 六、构建自检清单（每次推之前过一遍）

| 检查项 | 怎么看 |
|---|---|
| 图片处理生效 | 构建日志 `Processed images` 不为 0 |
| 首页是摘要 | `public/index.html` 里各条目摘要几百字，不是几千字 |
| 图片不变形 | 浏览器里看，宽高比例正常（见坑 2 的 CSS 是否在） |
| 标题全中文 | 分类页、标签页、404 页、归档页大标题都是中文 |
| 无残留旧内容 | 删过的文章，`public/posts/` 下不应再有对应目录 |
| 样式覆盖已合并 | `public/assets/css/*.css` 里能搜到 `assets/css/extended/custom.css` 的内容 |

---

## 七、文件位置速查

| 想改什么 | 改哪个文件 |
|---|---|
| 站点名、菜单、favicon、Toc 开关 | `hugo.toml` |
| 自己加的 CSS | `assets/css/extended/custom.css` |
| 正文图片渲染规则 | `layouts/_markup/render-image.html` |
| 页脚脚本（滚动节流等） | `layouts/_partials/extend_footer.html` |
| 404 页外观 | `layouts/404.html` |
| 分类/标签/404 页标题 | `content/` 下对应的 `_index.md` / `404.md` |
| 文章 | `content/posts/xxx.md` |
| 图片 | `assets/images/xxx.jpg` |
| 自动部署脚本 | `.github/workflows/hugo.yml`（一般不用动） |

---

## 八、绝对不要做的事

1. ❌ 不要改 `themes/` 里的任何文件（用 `layouts/` 覆盖代替）
2. ❌ 不要把图片放 `static/`（放 `assets/images/`）
3. ❌ 不要在 front matter 的 `cover.image` 前加斜杠
4. ❌ 不要以为改了 `hugo.toml` 的 `summaryLength` 就能截断中文摘要（要靠 `<!--more-->`）
5. ❌ 不要用不带 `--environment production` 的本地预览来判断图片改动是否生效
6. ❌ 不要因为 git 报 `broken` 就重装 git 或重新 clone（先查 `.git/HEAD`）
7. ❌ 不要用 `curl` 直接测网络连通性（先加 `--noproxy '*'`）
8. ❌ **不要为"未来可能会写"的内容预建分类/标签**（见第五节，会产出空页面）
9. ❌ **不要擅自新增、改名分类和标签**——先看第五节 5.1 的判断标准，确实不够用才加
10. ❌ 不要重命名已定下的分类/标签（等于换了新分类，旧链接失效）

---

## 九、当前状态备注（2026-10-11）

- 正文图片已迁移到 `assets/images/`，封面与正文图均已启用响应式 srcset
- 已建 `assets/css/extended/custom.css`，修复图片拉伸变形
- 所有文章均已加 `<!--more-->` 摘要标记
- 分类/标签/404 页标题已汉化
- **分类标签体系已按"最小起步"原则重建**：分类 = `养生` / `AI`，标签 = `功法` / `健康`（见第五节）
- 已清理测试文章（焦虑迷茫怎么破、我究竟是什么、旧版静坐入门）
- 站桩/静坐两篇已配封面图（Unsplash 免费可商用实景图）
- 提交通道：本地 git 已修复可用（`main` 分支跟踪 `origin/main`）
- 已知可用令牌：数字花园令牌**只读**，不能用于推送

---

*本手册随站点演进持续更新。发现新的坑，就补进"十条铁律"里。*
*分类标签不够用时，按第五节 5.1 的标准判断后再加，并回来更新 5.2 的表格。*

