<script>
/**
 * A small bar chart for the admin dashboard, drawn with ChartJS (the only chart
 * library the spec allows).
 *
 * ChartJS draws onto a <canvas> with plain DOM code, so it cannot be driven by a
 * Vue template. Hence the lifecycle hooks: create the chart once the canvas
 * exists (mounted), and destroy it on the way out (beforeUnmount) so the
 * canvas is not leaked.
 */
import Chart from 'chart.js/auto'

export default {
  name: 'BarChart',
  props: {
    labels: { type: Array, required: true },
    values: { type: Array, required: true },
    label: { type: String, default: 'Bookings' },
  },
  data() {
    return { chart: null }
  },
  mounted() {
    this.chart = new Chart(this.$refs.canvas, {
      type: 'bar',
      data: {
        // Plain copies with [...]: ChartJS keeps and mutates these arrays
        // internally, and it should not be holding on to Vue's reactive proxies.
        labels: [...this.labels],
        datasets: [
          {
            label: this.label,
            data: [...this.values],
            backgroundColor: '#198754', // Bootstrap's success green
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        // No grow animation: the numbers are a snapshot, not a live feed.
        animation: false,
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      },
    })
  },
  beforeUnmount() {
    if (this.chart) this.chart.destroy()
  },
}
</script>

<template>
  <!-- A fixed height is needed because maintainAspectRatio is off. -->
  <div style="height: 260px">
    <canvas ref="canvas"></canvas>
  </div>
</template>
