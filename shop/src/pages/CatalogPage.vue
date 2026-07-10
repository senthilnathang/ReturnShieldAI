<script setup>
import { onMounted, computed } from 'vue'
import { useShopStore } from '../store/shop'
import { ShoppingCart, Loader } from '../components/icons.js'

const store = useShopStore()
const products = computed(() =>
  store.activeCategory === 'all' ? store.products : store.products.filter((p) => p.category === store.activeCategory)
)

onMounted(() => {
  if (!store.products.length) store.loadCatalog()
})
</script>

<template>
  <section class="mb-6">
    <div class="rounded-3xl bg-gradient-to-br from-brand-600 to-indigo-700 px-6 py-8 text-white sm:px-8 sm:py-10">
      <h1 class="text-2xl font-extrabold tracking-tight sm:text-3xl">Shop with confidence.</h1>
      <p class="mt-2 max-w-xl text-sm text-indigo-100">
        Browse the catalog, check out with a mock payment, then return any item through ReturnShield AI's
        fraud-aware return engine — complete with image verification.
      </p>
    </div>
  </section>

  <div class="mb-5 flex flex-wrap gap-2">
    <button
      v-for="cat in store.categories"
      :key="cat"
      @click="store.activeCategory = cat"
      :class="['badge px-3.5 py-1.5 capitalize transition', store.activeCategory === cat ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50']"
    >
      {{ cat }}
    </button>
  </div>

  <div v-if="store.loadingProducts" class="grid place-items-center py-24 text-slate-400">
    <Loader class="h-7 w-7 animate-spin" />
  </div>

  <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    <article v-for="p in products" :key="p.id" class="card overflow-hidden transition hover:shadow-md">
      <div class="relative">
        <img :src="p.image" :alt="p.name" class="h-48 w-full object-cover" />
        <span v-if="p.tag" class="badge absolute left-3 top-3 bg-white/90 text-brand-700 shadow-sm">{{ p.tag }}</span>
      </div>
      <div class="p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="font-semibold leading-tight text-slate-900">{{ p.name }}</h3>
            <p class="mt-0.5 text-xs capitalize text-slate-500">{{ p.category }}</p>
          </div>
          <div class="text-right">
            <div class="text-lg font-bold">${{ p.price.toFixed(2) }}</div>
          </div>
        </div>
        <button @click="store.addToCart(p)" class="btn-primary mt-4 w-full">
          <ShoppingCart class="h-4 w-4" /> Add to cart
        </button>
      </div>
    </article>
  </div>
</template>
