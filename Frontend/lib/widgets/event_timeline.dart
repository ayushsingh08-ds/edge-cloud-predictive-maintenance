import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/widgets/event_tile.dart';

class EventTimeline extends StatelessWidget {
  const EventTimeline({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: AppTheme.clayDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'System Event Timeline',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                'Today',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textMuted,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          const EventTile(
            time: '14:22',
            event: 'Predictive Maintenance Alert: Machine #04 high vibration',
            priority: 'Critical',
            isAlert: true,
          ),
          const EventTile(
            time: '13:05',
            event: 'Job #842 batch processing station C complete',
            priority: 'Normal',
          ),
          const EventTile(
            time: '11:45',
            event: 'RL Model Update: Optimized throughput v2.4 deployed',
            priority: 'Medium',
          ),
          const EventTile(
            time: '09:12',
            event: 'Automatic system health check passed (20/20 assets)',
            priority: 'Normal',
          ),
          const EventTile(
            time: '08:00',
            event: 'Morning diagnostic shift hand-over complete',
            priority: 'Normal',
          ),
          const SizedBox(height: 12),
          Center(
            child: TextButton(
              onPressed: () {},
              child: Text(
                'View All Events History',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.sageGreen,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
