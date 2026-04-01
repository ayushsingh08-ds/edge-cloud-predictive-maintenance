import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';

class EventTile extends StatelessWidget {
  final String time;
  final String event;
  final String priority;
  final bool isAlert;

  const EventTile({
    super.key,
    required this.time,
    required this.event,
    required this.priority,
    this.isAlert = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isAlert ? Colors.orange.withOpacity(0.05) : AppTheme.surfaceLayer.withOpacity(0.3),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: isAlert ? Colors.orange.withOpacity(0.1) : Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              time,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w700,
                    color: isAlert ? Colors.orange : AppTheme.textMuted,
                    fontFeatures: [const FontFeature.tabularFigures()],
                  ),
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Text(
              event,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: isAlert ? FontWeight.w600 : FontWeight.w400,
                    color: AppTheme.textMain,
                  ),
            ),
          ),
          const SizedBox(width: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: isAlert ? Colors.orange.withOpacity(0.1) : AppTheme.surfaceLayer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              priority,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: isAlert ? Colors.orange : AppTheme.textMuted,
                    fontWeight: FontWeight.w600,
                    fontSize: 10,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
