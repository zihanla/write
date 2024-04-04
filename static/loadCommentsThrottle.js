// 节流函数，减少事件被高频触发
function throttle(func, wait) {
    var timeout;
    return function () {
        var context = this;
        var args = arguments;
        if (!timeout) {
            timeout = setTimeout(function () {
                timeout = null;
                func.apply(context, args);
            }, wait);
        }
    };
}

var scriptLoaded = false; // 确保脚本只加载一次

var loadScript = throttle(function () {
    if (scriptLoaded) return; // 如果脚本已加载，则直接返回

    var comments = document.querySelector("#comments");
    if (comments) {
        var commentsRect = comments.getBoundingClientRect();
        // 如果 #comments 在视口内或页面高度小于视口高度时加载脚本
        if (commentsRect.top <= window.innerHeight || document.documentElement.scrollHeight <= window.innerHeight) {
            scriptLoaded = true; // 设置标志位
            var script = document.createElement("script");
            script.src = "https://cusdis.com/js/cusdis.es.js";
            script.async = true;
            script.defer = true;
            document.body.appendChild(script);
            // 加载脚本后移除事件监听器
            window.removeEventListener("scroll", loadScript);
            window.removeEventListener("load", loadScript);
        }
    }
}, 200);

// 在 window 加载完成后尝试加载评论脚本
window.addEventListener("load", loadScript);

// 在滚动时也尝试加载评论脚本
window.addEventListener("scroll", loadScript);
