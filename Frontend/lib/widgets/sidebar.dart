import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';


class Sidebar extends StatelessWidget {
  final int selectedIndex;
  final Function(int) onItemSelected;

  const Sidebar({
    super.key,
    required this.selectedIndex,
    required this.onItemSelected,
  });

  static const double width = 230.0;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(height: 10),
          _NavItem(
            icon: Icons.dashboard,
            label: 'Overview',
            isActive: selectedIndex == 0,
            onTap: () => onItemSelected(0),
          ),
          _NavItem(
            icon: Icons.memory,
            label: 'Machines',
            isActive: selectedIndex == 1,
            onTap: () => onItemSelected(1),
          ),
          _NavItem(
            icon: Icons.work,
            label: 'Jobs',
            isActive: selectedIndex == 2,
            onTap: () => onItemSelected(2),
          ),
          _NavItem(
            icon: Icons.warning,
            label: 'Anomalies',
            isActive: selectedIndex == 3,
            onTap: () => onItemSelected(3),
          ),
          _NavItem(
            icon: Icons.play_circle_outline,
            label: 'Simulation',
            isActive: selectedIndex == 4,
            onTap: () => onItemSelected(4),
          ),
          _NavItem(
            icon: Icons.psychology,
            label: 'RL Training',
            isActive: selectedIndex == 5,
            onTap: () => onItemSelected(5),
          ),
          _NavItem(
            icon: Icons.bar_chart,
            label: 'Analytics',
            isActive: selectedIndex == 6,
            onTap: () => onItemSelected(6),
          ),
          _NavItem(
            icon: Icons.settings,
            label: 'System',
            isActive: selectedIndex == 7,
            onTap: () => onItemSelected(7),
          ),
          Spacer(),
          _NavItem(
            icon: Icons.logout,
            label: 'Logout',
            isActive: false,
            onTap: () {},
          ),
        ],
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isActive ? AppTheme.sageGreen.withOpacity(0.1) : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 20,
              color: isActive ? AppTheme.sageGreen : AppTheme.textMuted,
            ),
            const SizedBox(width: 14),
            Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                    color: isActive ? AppTheme.sageGreen : AppTheme.textMuted,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}
