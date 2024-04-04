// loadCommentsThrottle.js 文件内容

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

var loadScript = throttle(function () {
    var comments = document.querySelector("#comments");
    var commentsRect = comments.getBoundingClientRect();
    if (commentsRect.top <= window.innerHeight) {
        var script = document.createElement("script");
        script.src = "https://cusdis.hyx.ink/js/cusdis.es.js";
        script.async = true;
        script.defer = true;
        document.body.appendChild(script);
        window.removeEventListener("scroll", loadScript);
    }
}, 200); // scroll事件触发的间隔时间

window.addEventListener("scroll", loadScript);