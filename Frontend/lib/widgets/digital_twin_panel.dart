import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';


class DigitalTwinPanel extends StatelessWidget {
  const DigitalTwinPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 440,
      decoration: AppTheme.clayDecoration(),
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.sageGreen.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(Icons.factory, size: 20, color: AppTheme.sageGreen),
                  ),
                  const SizedBox(width: 16),
                  Text(
                    'Digital Twin',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ],
              ),
              Row(
                children: [
                  _PanelActionButton(icon: Icons.layers, label: 'Layers', onTap: () {}),
                  const SizedBox(width: 8),
                  _PanelActionButton(icon: Icons.fullscreen, label: 'Full', onTap: () {}),
                ],
              ),
            ],
          ),
          const SizedBox(height: 28),
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppTheme.surfaceLayer.withOpacity(0.4),
                borderRadius: BorderRadius.circular(28),
                border: Border.all(
                  color: Colors.white.withOpacity(0.5),
                  width: 2,
                ),
              ),
              child: Stack(
                children: [
                  Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.account_tree,
                          size: 48,
                          color: AppTheme.sageGreen.withOpacity(0.2),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Factory Graph Visualization',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: AppTheme.textMuted,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Initializing synchronization engine...',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: AppTheme.textMuted.withOpacity(0.6),
                              ),
                        ),
                      ],
                    ),
                  ),
                  // Decorative grid overlay
                  Positioned.fill(
                    child: Opacity(
                      opacity: 0.03,
                      child: CustomPaint(
                        painter: GridPainter(),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PanelActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _PanelActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            Icon(icon, size: 14, color: AppTheme.textMuted),
            const SizedBox(width: 6),
            Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                    color: AppTheme.textMuted,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.textMuted
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    for (var i = 0.0; i <= size.width; i += 40) {
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    }
    for (var i = 0.0; i <= size.height; i += 40) {
      canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}
