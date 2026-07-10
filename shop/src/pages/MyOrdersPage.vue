<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useShopStore } from '../store/shop'
import { Package, ArrowRight, Loader } from '../components/icons.js'

const store = useShopStore()
const router = useRouter()
const loading = ref(false)

onMounted(async () => {
  if (!store.customer?.customer_id) return
  loading.value = true
  try {
    await store.loadOrders()
  } finally {
    loading.value = false
  }
})

const orders = computed(() => store.orders)
</script>

<template>
  <section>
    <div class="mb-5 flex items-center justify-between">
      <h1 class="text-xl font-bold">My orders</h1>
      <button @click="store.loadOrders()" class="btn-ghost text-xs">Refresh</button>
    </div>

    <div v-if="!store.customer?.customer_id" class="card p-10 text-center text-slate-500">
      <Package class="mx-auto h-8 w-8 text-slate-300" />
      <p class="mt-3">No orders yet. Place an order to see it here.</p>
      <button @click="router.push('/shop')" class="btn-primary mt-4">Start shopping</button>
    </div>

    <div v-else-if="loading" class="grid place-items-center py-16 text-slate-400">
      <Loader class="h-6 w-6 animate-spin" />
    </div>

    <div v-else-if="!orders.length" class="card p-10 text-center text-slate-500">
      <p>No orders found for this session.</p>
    </div>

    <div v-else class="space-y-3">
      <div v-for="o in orders" :key="o.order_id" class="card flex items-center gap-4 p-4">
        <img :src="`data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='56' height='56'><rect width='56' height='56' fill='%23eef2ff' rx='12'/></svg>`" class="h-12 w-12 rounded-xl" />
        <div class="min-w-0 flex-1">
          <div class="truncate font-semibold">{{ o.product_name }}</div>
          <div class="text-xs text-slate-500">{{ o.external_order_id }} · {{ o.category }} · Qty {{ o.quantity }}</div>
        </div>
        <div class="hidden text-right sm:block">
          <div class="text-sm font-bold">${{ Number(o.product_value).toFixed(2) }}</div>
          <span class="badge mt-1 bg-emerald-50 text-emerald-700">{{ o.order_status }}</span>
        </div>
        <button @click="router.push(`/orders/${o.order_id}`)" class="btn-dark">
          Details <ArrowRight class="h-4 w-4" />
        </button>
      </div>
    </div>
  </section>
</template>
