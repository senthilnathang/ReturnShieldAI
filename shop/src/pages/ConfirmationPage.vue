<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useShopStore } from '../store/shop'
import { CheckCircle, ArrowRight, Package } from '../components/icons.js'

const props = defineProps({ txn: { type: String, required: true } })
const store = useShopStore()
const router = useRouter()
const orders = ref([])

onMounted(async () => {
  if (store.customer?.customer_id) {
    await store.loadOrders()
    orders.value = store.orders.slice(0, 4)
  }
})
</script>

<template>
  <section class="mx-auto max-w-2xl text-center">
    <div class="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-100 text-emerald-600">
      <CheckCircle class="h-8 w-8" />
    </div>
    <h1 class="mt-5 text-2xl font-extrabold tracking-tight">Order confirmed!</h1>
    <p class="mt-2 text-sm text-slate-500">
      Transaction <span class="font-mono text-slate-700">{{ props.txn }}</span> · Paid
      <span class="font-semibold text-slate-700">${{ store.customer?.total?.toFixed(2) ?? '0.00' }}</span>
    </p>
    <p class="mt-1 text-xs text-slate-400">
      For this demo your order is instantly marked <strong>delivered</strong>, so you can immediately start a return.
    </p>

    <div class="mt-6 flex flex-wrap justify-center gap-3">
      <button @click="router.push('/orders')" class="btn-dark">
        <Package class="h-4 w-4" /> View my orders
      </button>
      <button @click="router.push('/shop')" class="btn-ghost">
        Keep shopping <ArrowRight class="h-4 w-4" />
      </button>
    </div>
  </section>

  <section v-if="orders.length" class="mt-10">
    <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">In this order</h2>
    <div class="grid gap-3 sm:grid-cols-2">
      <div v-for="o in orders" :key="o.order_id" class="card flex items-center gap-3 p-3">
        <img :src="`data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><rect width='64' height='64' fill='%23eef2ff' rx='12'/></svg>`" class="h-12 w-12 rounded-lg" />
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-semibold">{{ o.product_name }}</div>
          <div class="text-xs text-slate-500">{{ o.external_order_id }} · Qty {{ o.quantity }}</div>
        </div>
        <button @click="router.push(`/orders/${o.order_id}`)" class="btn-ghost text-xs">Details</button>
      </div>
    </div>
  </section>
</template>
