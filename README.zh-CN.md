> 测试环境：Windows x64 用于 APK 静态检查，GitHub Actions Ubuntu 用于构建；Android 真机上的公式显示尚待验证。
>
> [English README](README.md)

# Herald：矩阵公式修复分支

本仓库 fork 自 [Giton22/herald](https://github.com/Giton22/herald)，修复 Android 压缩构建中矩阵公式显示为原始 TeX 的问题。

## 修复内容

Herald 使用 JLaTeXMath 渲染数学公式。该库通过 Java 反射实例化 `NewCommandMacro` 并调用 `executeMacro`；R8 会删除或改名这些没有直接调用的成员。结果是简单公式可以显示，`pmatrix` 等需要宏展开的矩阵环境却会失败。

修复只保留该类的公开无参构造函数和指定回调，不关闭整个应用的混淆或压缩。

新增的 APK 回归检查直接读取 DEX，确认上述反射入口在压缩后仍然存在。原版官方 `0.13.0` arm64 APK 无法通过此检查。检查压缩产物不能替代手机上的排版验收。

## 安装与使用

在本仓库 **Actions → CI** 的成功运行中下载 `herald-matrix-fix-dev`，解压得到 APK。

该产物使用项目原有的 **Herald Dev** 构建类型，应用标识为 `dev.herald.android.dev`，可与原版 Herald 并存。首次打开需重新登录已有的 Hermes Dashboard；保持原来的网关地址和 `default` profile 即可。

手机上请检查列向量、矩阵组成的基、行内公式及多行公式。该修复不改变 Hermes 的会话数据库、模型配置或网关设置。

## 构建和检查

需要 JDK 25、Android SDK API 37 和项目自带的 Gradle wrapper。依赖优先使用国内镜像，官方仓库保留为回退来源：

```bash
./gradlew --no-daemon --init-script scripts/android-mirrors.init.gradle :androidApp:assembleDev -PappVersion=0.13.0-matrix.1
python3 scripts/check-math-reflection.py androidApp/build/outputs/apk/dev/androidApp-dev.apk
```

CI 同时执行上游已有的单元测试、debug 构建和 lint，并额外构建、检查和上传压缩后的 Dev APK。

关于项目完整功能、手机连接和隐私说明，请阅读 [上游项目说明](README.md)。
