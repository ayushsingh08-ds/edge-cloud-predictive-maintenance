import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';

class KpiCard extends StatelessWidget {
  final String title;
  final String value;
  final String trend;
  final bool isTrendPositive;
  final IconData? icon;

  const KpiCard({
    super.key,
    required this.title,
    required this.value,
    required this.trend,
    this.isTrendPositive = true,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.clayDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Icon(
              icon,
              size: 20,
              color: AppTheme.sageGreen,
            ),
            const SizedBox(height: 12),
          ],
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textMuted,
                  fontWeight: FontWeight.w500,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textMain,
                  letterSpacing: -0.5,
                ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(
                isTrendPositive ? Icons.trending_up : Icons.trending_down,
                size: 14,
                color: isTrendPositive ? AppTheme.sageGreen : Colors.orangeAccent,
              ),
              const SizedBox(width: 4),
              Text(
                trend,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: isTrendPositive ? AppTheme.sageGreen : Colors.orangeAccent,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
