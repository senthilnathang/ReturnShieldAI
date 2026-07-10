<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useShopStore } from '../store/shop'
import { Plus, Minus, Trash, ShoppingCart, ArrowRight } from '../components/icons.js'

const store = useShopStore()
const router = useRouter()
const items = computed(() => store.cartItemsDetailed)
</script>

<template>
  <section v-if="!items.length" class="grid place-items-center py-24 text-center">
    <div>
      <div class="mx-auto grid h-16 w-16 place-items-center rounded-full bg-slate-100 text-slate-400">
        <ShoppingCart class="h-7 w-7" />
      </div>
      <h2 class="mt-4 text-lg font-semibold text-slate-700">Your cart is empty</h2>
      <p class="mt-1 text-sm text-slate-500">Add a few products to get started.</p>
      <button @click="router.push('/shop')" class="btn-primary mt-5">Browse products</button>
    </div>
  </section>

  <section v-else class="grid gap-6 lg:grid-cols-[1.6fr_0.9fr]">
    <div class="space-y-3">
      <h1 class="text-xl font-bold">Your cart</h1>
      <div v-for="i in items" :key="i.product_id" class="card flex items-center gap-4 p-3">
        <img :src="i.image" :alt="i.name" class="h-16 w-16 rounded-xl object-cover" />
        <div class="min-w-0 flex-1">
          <div class="truncate font-semibold text-slate-900">{{ i.name }}</div>
          <div class="text-sm text-slate-500">${{ i.price.toFixed(2) }} each</div>
          <div class="mt-2 flex items-center gap-2">
            <button @click="store.setQty(i.product_id, i.quantity - 1)" class="grid h-7 w-7 place-items-center rounded-lg ring-1 ring-slate-200 hover:bg-slate-50"><Minus class="h-3.5 w-3.5" /></button>
            <span class="w-8 text-center text-sm font-semibold">{{ i.quantity }}</span>
            <button @click="store.setQty(i.product_id, i.quantity + 1)" class="grid h-7 w-7 place-items-center rounded-lg ring-1 ring-slate-200 hover:bg-slate-50"><Plus class="h-3.5 w-3.5" /></button>
            <button @click="store.removeFromCart(i.product_id)" class="ml-2 grid h-7 w-7 place-items-center rounded-lg text-rose-500 ring-1 ring-rose-100 hover:bg-rose-50"><Trash class="h-3.5 w-3.5" /></button>
          </div>
        </div>
        <div class="text-right font-bold">${{ (i.price * i.quantity).toFixed(2) }}</div>
      </div>
    </div>

    <aside class="card h-fit p-5 lg:sticky lg:top-24">
      <h2 class="text-base font-semibold">Order summary</h2>
      <dl class="mt-4 space-y-2 text-sm">
        <div class="flex justify-between"><dt class="text-slate-500">Subtotal</dt><dd>${{ store.cartTotal.toFixed(2) }}</dd></div>
        <div class="flex justify-between"><dt class="text-slate-500">Shipping</dt><dd class="text-emerald-600">Free</dd></div>
        <div class="flex justify-between border-t border-slate-100 pt-3 text-base font-bold"><dt>Total</dt><dd>${{ store.cartTotal.toFixed(2) }}</dd></div>
      </dl>
      <button @click="router.push('/checkout')" class="btn-dark mt-5 w-full">
        Checkout <ArrowRight class="h-4 w-4" />
      </button>
      <p class="mt-3 text-center text-[11px] text-slate-400">Mock payment — no real card is charged.</p>
    </aside>
  </section>
</template>
