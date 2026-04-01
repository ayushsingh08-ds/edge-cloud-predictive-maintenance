import 'dart:async';
import 'package:flutter/material.dart';
import 'package:frontend/theme/app_theme.dart';

import 'package:intl/intl.dart';

class TopBar extends StatefulWidget {
  final bool isSimulationRunning;
  final VoidCallback onStartSimulation;
  final VoidCallback onSettings;
  final VoidCallback onProfile;

  const TopBar({
    super.key,
    required this.isSimulationRunning,
    required this.onStartSimulation,
    required this.onSettings,
    required this.onProfile,
  });

  @override
  State<TopBar> createState() => _TopBarState();
}

class _TopBarState extends State<TopBar> {
  late Timer _timer;
  String _currentTime = '';

  @override
  void initState() {
    super.initState();
    _updateTime();
    _timer = Timer.periodic(const Duration(seconds: 1), (Timer t) => _updateTime());
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  void _updateTime() {
    final DateTime now = DateTime.now();
    final String formattedTime = DateFormat('HH:mm:ss').format(now);
    if (mounted) {
      setState(() {
        _currentTime = formattedTime;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: const BoxDecoration(
        color: Colors.transparent,
      ),
      child: Row(
        children: [
          // Dashboard Title
          Text(
            'Factory Control Dashboard',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  fontSize: 18,
                ),
          ),
          const SizedBox(width: 48),

          // Current Time
          Row(
            children: [
              Icon(Icons.access_time, size: 16, color: AppTheme.textMuted),
              const SizedBox(width: 8),
              Text(
                _currentTime,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.textMuted,
                      fontWeight: FontWeight.w500,
                      fontFeatures: [const FontFeature.tabularFigures()],
                    ),
              ),
            ],
          ),
          const Spacer(),

          // Simulation Status Indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.surfaceLayer,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: widget.isSimulationRunning ? AppTheme.sageGreen : Colors.redAccent,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  widget.isSimulationRunning ? 'Running' : 'Stopped',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textMain,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),

          // Start Simulation Button
          ElevatedButton(
            onPressed: widget.onStartSimulation,
            style: ElevatedButton.styleFrom(
              backgroundColor: widget.isSimulationRunning ? Colors.white : AppTheme.sageGreen,
              foregroundColor: widget.isSimulationRunning ? AppTheme.textMain : Colors.white,
              elevation: 0,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              minimumSize: const Size(0, 40),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: widget.isSimulationRunning 
                    ? BorderSide(color: AppTheme.textMuted.withOpacity(0.2)) 
                    : BorderSide.none,
              ),
            ),
            child: Text(widget.isSimulationRunning ? 'Stop Simulation' : 'Start Simulation'),
          ),
          const SizedBox(width: 16),

          // Settings Button
          _TopBarIconButton(
            icon: Icons.settings,
            onPressed: widget.onSettings,
          ),
          const SizedBox(width: 8),

          // User Profile
          InkWell(
            onTap: widget.onProfile,
            borderRadius: BorderRadius.circular(20),
            child: CircleAvatar(
              radius: 18,
              backgroundColor: AppTheme.surfaceLayer,
              child: const Placeholder(fallbackHeight: 18, fallbackWidth: 18),
            ),
          ),
        ],
      ),
    );
  }
}

class _TopBarIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onPressed;

  const _TopBarIconButton({
    required this.icon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onPressed,
      icon: Icon(icon, size: 20, color: AppTheme.textMuted),
      style: IconButton.styleFrom(
        padding: const EdgeInsets.all(8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}
