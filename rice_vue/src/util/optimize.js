// 防抖函数
export function debounce(func, timer) {
    let timeout;
    return () => {
        if(timeout) clearTimeout(timeout);
        timeout = setTimeout(() => func(), timer);
    }
}

// 节流函数
export function throttle(func, timer) {
    let lastTime = 0;
    return (...args) => {
        const nowtime = Date.now();
        if(nowtime - lastTime >= timer) {
            func(...args);
            lastTime = nowtime;
        }
    }
}
