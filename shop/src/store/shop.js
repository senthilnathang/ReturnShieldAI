import { defineStore } from 'pinia'
import { api } from '../api/client'

const STORAGE_CART = 'shop.cart'
const STORAGE_CUSTOMER = 'shop.customer'

export const useShopStore = defineStore('shop', {
  state: () => ({
    products: [],
    categories: [],
    loadingProducts: false,
    cart: JSON.parse(localStorage.getItem(STORAGE_CART) || '[]'),
    activeCategory: 'all',
    customer: JSON.parse(localStorage.getItem(STORAGE_CUSTOMER) || 'null'),
    orders: [],
  }),
  getters: {
    cartCount: (s) => s.cart.reduce((n, i) => n + i.quantity, 0),
    cartTotal: (s) => s.cart.reduce((sum, i) => sum + i.price * i.quantity, 0),
    cartItemsDetailed: (s) =>
      s.cart.map((i) => {
        const p = s.products.find((x) => x.id === i.product_id)
        return { ...i, product: p }
      }),
  },
  actions: {
    async loadCatalog() {
      this.loadingProducts = true
      try {
        const [products, categories] = await Promise.all([api.getProducts(), api.getCategories()])
        this.products = products
        this.categories = ['all', ...categories]
      } finally {
        this.loadingProducts = false
      }
    },
    addToCart(product, quantity = 1) {
      const existing = this.cart.find((i) => i.product_id === product.id)
      if (existing) {
        existing.quantity += quantity
      } else {
        this.cart.push({ product_id: product.id, name: product.name, price: product.price, category: product.category, image: product.image, quantity })
      }
      this.persistCart()
    },
    setQty(product_id, quantity) {
      const item = this.cart.find((i) => i.product_id === product_id)
      if (!item) return
      item.quantity = Math.max(1, quantity)
      this.persistCart()
    },
    removeFromCart(product_id) {
      this.cart = this.cart.filter((i) => i.product_id !== product_id)
      this.persistCart()
    },
    clearCart() {
      this.cart = []
      this.persistCart()
    },
    persistCart() {
      localStorage.setItem(STORAGE_CART, JSON.stringify(this.cart))
    },
    setCustomer(customer) {
      this.customer = customer
      localStorage.setItem(STORAGE_CUSTOMER, JSON.stringify(customer))
    },
    async loadOrders() {
      if (!this.customer?.customer_id) {
        this.orders = []
        return
      }
      this.orders = await api.getCustomerOrders(this.customer.customer_id)
    },
    logout() {
      this.customer = null
      this.orders = []
      localStorage.removeItem(STORAGE_CUSTOMER)
    },
  },
})
