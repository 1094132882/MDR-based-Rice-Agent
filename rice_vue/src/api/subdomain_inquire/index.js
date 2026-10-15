import request from '../../util/request'
import { getToken, removeToken } from "../../util/auth";

// 获取子域首页数据
export function getSubdomainList(){
    return request({
        method: "get",
        url: "/mfi/getSubdomainList",
    })
}

// 获取子页面信息
export function getSubdomainByIdentifier(id){
    return request({
        method: "get",
        url: "/mdr/getSubdomainByIdentifier",
        params: {
            identifier : id
        }
    })
}

// 分页查询
export function geTablesBySubdomainIdentifierAndDatasetIdentifier(subdomain_identifier,dataset_identifier,page){
    return request({
        method: "get",
        url: "/mfi/geTablesBySubdomainIdentifierAndDatasetIdentifier",
        params:{
            subdomain_identifier: subdomain_identifier,
            dataset_identifier: dataset_identifier,
            page:page
        }
    })
}