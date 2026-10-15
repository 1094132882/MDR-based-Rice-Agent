import { createRouter, createWebHistory } from "vue-router";

const routes = [
    {
        path: "/",
        redirect: "/home_page",
        name: "Banner",
        component: ()=> import("../views/index.vue"),
        children:[
            {
                path: "home_page",
                name: "home_page",
                component: () => import("../views/home_page/index.vue"),
            },
            {
                path: "metadata_inquire",
                name: "metadata_inquire",
                component: () => import("../views/metadata_inquire/index.vue"),
            },
            {
                path: "subdomain_inquire",
                name: "subdomain_inquire",
                component: () => import("../views/subdomain_inquire/index.vue"),
            },
            {
                path: "aiChat",
                name: "aiChat",
                component: () => import("../views/aichat/index.vue"),
            },
            {
                path: "rice_graphTable",
                name: "rice_graphTable",
                component: () => import("../views/rice_graphTable/index.vue")
            }
        ]

    },
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

export default router;
