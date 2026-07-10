<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useShopStore } from './store/shop'
import { ShoppingBag, ShoppingCart, Package, Store, LogOut } from './components/icons.js'

const store = useShopStore()
const router = useRouter()
const count = computed(() => store.cartCount)
const hasCustomer = computed(() => !!store.customer)

function logout() {
  store.logout()
  router.push('/shop')
}
</script>

<template>
  <div class="min-h-screen">
    <header class="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <RouterLink to="/shop" class="flex items-center gap-2">
          <span class="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white">
            <Store class="h-5 w-5" />
          </span>
          <div class="leading-tight">
            <div class="text-base font-extrabold tracking-tight">ShieldShop</div>
            <div class="text-[11px] text-slate-500">Demo storefront</div>
          </div>
        </RouterLink>

        <nav class="flex items-center gap-1 sm:gap-2">
          <RouterLink to="/shop" class="btn-ghost hidden sm:inline-flex">
            <ShoppingBag class="h-4 w-4" /> Shop
          </RouterLink>
          <RouterLink to="/orders" class="btn-ghost">
            <Package class="h-4 w-4" /> Orders
          </RouterLink>
          <RouterLink to="/cart" class="btn-dark relative">
            <ShoppingCart class="h-4 w-4" />
            <span class="hidden sm:inline">Cart</span>
            <span v-if="count" class="absolute -right-1.5 -top-1.5 grid h-5 min-w-[1.25rem] place-items-center rounded-full bg-rose-500 px-1 text-[11px] font-bold text-white">{{ count }}</span>
          </RouterLink>
          <button v-if="hasCustomer" @click="logout" class="btn-ghost" title="Reset demo session">
            <LogOut class="h-4 w-4" />
          </button>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <RouterView />
    </main>

    <footer class="mx-auto max-w-6xl px-4 pb-10 pt-6 text-center text-xs text-slate-400 sm:px-6">
      ShieldShop — a demo Vue storefront wired to the ReturnShield AI return engine. No real payments are processed.
    </footer>
  </div>
</template>
