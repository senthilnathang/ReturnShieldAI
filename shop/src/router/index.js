import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', redirect: '/shop' },
  { path: '/shop', name: 'catalog', component: () => import('../pages/CatalogPage.vue') },
  { path: '/cart', name: 'cart', component: () => import('../pages/CartPage.vue') },
  { path: '/checkout', name: 'checkout', component: () => import('../pages/CheckoutPage.vue') },
  { path: '/confirmation/:txn', name: 'confirmation', component: () => import('../pages/ConfirmationPage.vue'), props: true },
  { path: '/orders', name: 'orders', component: () => import('../pages/MyOrdersPage.vue') },
  { path: '/orders/:orderId', name: 'order-detail', component: () => import('../pages/OrderDetailPage.vue'), props: true },
  { path: '/orders/:orderId/return', name: 'create-return', component: () => import('../pages/CreateReturnPage.vue'), props: true },
  { path: '/returns/:returnId', name: 'return-detail', component: () => import('../pages/ReturnDetailPage.vue'), props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})
