<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { ArrowLeft, ArrowRight, Shield, Loader, AlertTriangle } from '../components/icons.js'

const props = defineProps({ orderId: { type: String, required: true } })
const router = useRouter()

const order = ref(null)
const returns = ref([])
const eligibility = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [o, ret, elig] = await Promise.all([
      api.getOrder(props.orderId),
      api.getOrderReturns(props.orderId),
      api.getEligibility(props.orderId),
    ])
    order.value = o
    returns.value = ret.items || []
    eligibility.value = elig
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const canReturn = computed(() => eligibility.value?.eligible)
</script>

<template>
  <button @click="router.push('/orders')" class="btn-ghost mb-4 text-xs">
    <ArrowLeft class="h-4 w-4" /> Back to orders
  </button>

  <div v-if="loading" class="grid place-items-center py-20 text-slate-400">
    <Loader class="h-6 w-6 animate-spin" />
  </div>

  <div v-else-if="error" class="card border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
    <AlertTriangle class="mb-1 h-4 w-4" /> {{ error }}
  </div>

  <div v-else-if="order" class="space-y-6">
    <div class="card p-5">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div class="text-xs uppercase tracking-wide text-slate-500">Order</div>
          <h1 class="text-xl font-bold">{{ order.product_name }}</h1>
          <p class="mt-1 text-sm text-slate-500">{{ order.external_order_id }} · {{ order.category }}</p>
        </div>
        <div class="text-right">
          <div class="text-2xl font-extrabold">${{ Number(order.product_value).toFixed(2) }}</div>
          <span class="badge mt-1 bg-emerald-50 text-emerald-700">{{ order.order_status }}</span>
        </div>
      </div>
      <dl class="mt-5 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3 text-sm">
        <div><dt class="text-slate-400">Quantity</dt><dd class="font-medium">{{ order.quantity }}</dd></div>
        <div><dt class="text-slate-400">Payment</dt><dd class="font-medium capitalize">{{ order.payment_method }}</dd></div>
        <div><dt class="text-slate-400">Delivered</dt><dd class="font-medium">{{ order.delivery_date ? new Date(order.delivery_date).toLocaleDateString() : '—' }}</dd></div>
      </dl>
    </div>

    <div class="card flex flex-wrap items-center justify-between gap-4 p-5">
      <div class="flex items-start gap-3">
        <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl" :class="canReturn ? 'bg-brand-50 text-brand-600' : 'bg-amber-50 text-amber-600'">
          <Shield class="h-5 w-5" />
        </div>
        <div>
          <div class="font-semibold">{{ canReturn ? 'Returnable' : 'Not returnable' }}</div>
          <p class="text-sm text-slate-500">{{ eligibility?.message || (canReturn ? 'This order is eligible for return.' : '—') }}</p>
        </div>
      </div>
      <button v-if="canReturn" @click="router.push(`/orders/${props.orderId}/return`)" class="btn-dark">
        Start a return <ArrowRight class="h-4 w-4" />
      </button>
    </div>

    <div v-if="returns.length" class="card p-5">
      <h2 class="text-base font-semibold">Returns for this order</h2>
      <div class="mt-3 space-y-2">
        <button v-for="r in returns" :key="r.id" @click="router.push(`/returns/${r.id}`)"
          class="flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left hover:bg-slate-50">
          <div>
            <div class="font-medium">{{ r.external_return_id }}</div>
            <div class="text-xs text-slate-500">{{ r.return_reason_category }} · {{ r.return_status }}</div>
          </div>
          <div class="text-right">
            <span class="badge" :class="r.fraud_decision === 'HOLD_REFUND_HIGH_RISK' ? 'bg-rose-50 text-rose-700' : r.fraud_decision === 'MANUAL_REVIEW' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'">
              {{ r.fraud_decision || 'PENDING' }}
            </span>
            <div v-if="r.fraud_risk_score != null" class="mt-1 text-xs text-slate-500">Risk {{ r.fraud_risk_score.toFixed(1) }}</div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>
