import request from '../../util/request'
import { getToken, removeToken } from "../../util/auth";

// ai对话窗口
export function aiChat(content, session_id, language = "en"){
    return request({
        method: "get",
        url: "/qa/chat",
        params:{
            content:content,
            session_id:session_id,
            language:language
        },
        timeout: 0
    })
}

// ai默认对话
export function initChat(language = "en"){
    return request({
        method: "get",
        url: "/qa/initChat",
        params:{
            language:language
        }
    })
}
