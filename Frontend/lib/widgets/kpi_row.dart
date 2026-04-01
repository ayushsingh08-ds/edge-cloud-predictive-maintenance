import 'package:flutter/material.dart';
import 'package:frontend/widgets/kpi_card.dart';


class KpiRow extends StatelessWidget {
  const KpiRow({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        children: [
          SizedBox(
            width: 200,
            child: KpiCard(
              title: 'Throughput',
              value: '842',
              trend: '+12%',
              isTrendPositive: true,
              icon: Icons.trending_up,
            ),
          ),
          const SizedBox(width: 16),
          SizedBox(
            width: 200,
            child: KpiCard(
              title: 'Utilization',
              value: '91.4%',
              trend: '+2.4%',
              isTrendPositive: true,
              icon: Icons.monitor,
            ),
          ),
          const SizedBox(width: 16),
          SizedBox(
            width: 200,
            child: KpiCard(
              title: 'Downtime',
              value: '14m',
              trend: '-8.2%',
              isTrendPositive: true,
              icon: Icons.access_time,
            ),
          ),
          const SizedBox(width: 16),
          SizedBox(
            width: 200,
            child: KpiCard(
              title: 'Failure Rate',
              value: '0.24%',
              trend: '+0.01%',
              isTrendPositive: false,
              icon: Icons.warning,
            ),
          ),
          const SizedBox(width: 16),
          SizedBox(
            width: 200,
            child: KpiCard(
              title: 'Jobs Waiting',
              value: '12',
              trend: 'Stable',
              isTrendPositive: true,
              icon: Icons.format_list_numbered,
            ),
          ),
        ],
      ),
    );
  }
}
