<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { ArrowLeft, Shield, Loader, CheckCircle, AlertTriangle, Image as ImageIcon } from '../components/icons.js'

const props = defineProps({ returnId: { type: String, required: true } })
const router = useRouter()

const detail = ref(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    detail.value = await api.getReturnDetail(props.returnId)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const riskTone = computed(() => {
  const d = detail.value?.fraud_decision
  if (d === 'HOLD_REFUND_HIGH_RISK') return 'rose'
  if (d === 'MANUAL_REVIEW') return 'amber'
  return 'emerald'
})
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

  <div v-else-if="detail" class="space-y-5">
    <!-- Decision banner -->
    <div class="card overflow-hidden p-0">
      <div class="px-5 py-5" :class="{
        'bg-emerald-50': riskTone === 'emerald',
        'bg-amber-50': riskTone === 'amber',
        'bg-rose-50': riskTone === 'rose',
      }">
        <div class="flex items-center gap-3">
          <div class="grid h-11 w-11 place-items-center rounded-xl bg-white shadow-sm" :class="{
            'text-emerald-600': riskTone === 'emerald',
            'text-amber-600': riskTone === 'amber',
            'text-rose-600': riskTone === 'rose',
          }">
            <Shield class="h-5 w-5" />
          </div>
          <div>
            <div class="text-xs font-medium uppercase tracking-wide text-slate-500">Return decision</div>
            <div class="text-lg font-bold text-slate-900">{{ detail.fraud_decision || detail.fraud_screening_status || 'PENDING' }}</div>
          </div>
          <div v-if="detail.fraud_risk_score != null" class="ml-auto text-right">
            <div class="text-2xl font-extrabold">{{ detail.fraud_risk_score.toFixed(1) }}</div>
            <div class="text-[11px] text-slate-500">fraud risk</div>
          </div>
        </div>
      </div>
      <div class="grid gap-3 px-5 py-4 text-sm sm:grid-cols-3">
        <div><dt class="text-slate-400">Return ID</dt><dd class="font-mono">{{ detail.external_return_id }}</dd></div>
        <div><dt class="text-slate-400">Status</dt><dd class="font-medium">{{ detail.return_status }}</dd></div>
        <div><dt class="text-slate-400">Screening</dt><dd class="font-medium">{{ detail.fraud_screening_status }}</dd></div>
      </div>
    </div>

    <div class="grid gap-5 lg:grid-cols-2">
      <div class="card p-5">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Return details</h2>
        <dl class="mt-3 space-y-2 text-sm">
          <div class="flex justify-between"><dt class="text-slate-500">Reason</dt><dd class="font-medium text-right">{{ detail.return_reason_category }}</dd></div>
          <div class="flex justify-between"><dt class="text-slate-500">Condition</dt><dd class="font-medium capitalize">{{ detail.condition_reported }}</dd></div>
          <div class="flex justify-between"><dt class="text-slate-500">Method</dt><dd class="font-medium">{{ detail.return_method }}</dd></div>
          <div class="flex justify-between"><dt class="text-slate-500">Refund to</dt><dd class="font-medium">{{ detail.preferred_refund_method }}</dd></div>
          <div v-if="detail.refund_amount != null" class="flex justify-between"><dt class="text-slate-500">Refund amount</dt><dd class="font-bold text-emerald-600">${{ detail.refund_amount.toFixed(2) }}</dd></div>
        </dl>
        <p v-if="detail.detailed_description" class="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">{{ detail.detailed_description }}</p>
      </div>

      <div class="card p-5">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-500">Items returned</h2>
        <ul class="mt-3 space-y-2">
          <li v-for="i in detail.items" :key="i.id" class="flex items-center justify-between rounded-xl border border-slate-100 px-3 py-2 text-sm">
            <div>
              <div class="font-medium">{{ i.product_name }}</div>
              <div class="text-xs text-slate-500">SKU {{ i.sku }} · {{ i.item_match_status }}</div>
            </div>
            <span class="badge bg-slate-100 text-slate-600">Qty {{ i.quantity }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div class="card p-5">
      <h2 class="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        <ImageIcon class="h-4 w-4" /> Image verification
      </h2>
      <p v-if="!detail.timeline?.some((t) => t.label.includes('Image'))" class="mt-2 text-sm text-slate-500">No image was attached to this return.</p>
      <ul v-else class="mt-3 space-y-2 text-sm">
        <li v-for="t in detail.timeline" :key="t.label + t.time" class="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
          <span class="flex items-center gap-2">
            <CheckCircle v-if="t.label.includes('Completed')" class="h-4 w-4 text-emerald-500" />
            <AlertTriangle v-else-if="t.label.includes('Mismatch') || t.label.includes('Failed')" class="h-4 w-4 text-amber-500" />
            <Shield v-else class="h-4 w-4 text-slate-400" />
            {{ t.label }}
          </span>
          <span class="text-xs text-slate-400">{{ new Date(t.time).toLocaleString() }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>
