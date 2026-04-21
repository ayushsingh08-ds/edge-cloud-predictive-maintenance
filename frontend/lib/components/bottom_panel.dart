import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/layout_provider.dart';
import '../providers/simulation_provider.dart';
import 'neumorphic_theme.dart';

class BottomPanel extends StatefulWidget {
  const BottomPanel({Key? key}) : super(key: key);

  @override
  State<BottomPanel> createState() => _BottomPanelState();
}

class _BottomPanelState extends State<BottomPanel> {
  int _activeTabIndex = 0;

  static const List<String> _tabs = ['Alerts', 'Logs', 'Events', 'Scenarios'];

  @override
  Widget build(BuildContext context) {
    if (_activeTabIndex < 0 || _activeTabIndex >= _tabs.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        setState(() => _activeTabIndex = 0);
      });
    }
    final safeTabIndex =
        (_activeTabIndex < 0 || _activeTabIndex >= _tabs.length)
        ? 0
        : _activeTabIndex;

    final layout = Provider.of<LayoutProvider>(context);
    final simulation = Provider.of<SimulationProvider>(context);
    final metrics = simulation.globalMetrics;

    return Container(
      height: 230,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      decoration: NeumorphicTheme.decoration(
        isDark: layout.isDarkMode,
        borderRadius: BorderRadius.zero,
      ),
      child: Column(
        children: [
          Row(
            children: [
              _buildTabArea(simulation, layout.isDarkMode, safeTabIndex),
              const Spacer(),
              _buildSystemMetrics(metrics, simulation, layout.isDarkMode),
            ],
          ),
          const SizedBox(height: 10),
          Expanded(
            child: _buildActiveTabContent(
              simulation,
              layout.isDarkMode,
              safeTabIndex,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabArea(
    SimulationProvider provider,
    bool isDark,
    int safeTabIndex,
  ) {
    return Row(
      children: List.generate(_tabs.length, (index) {
        final label = _tabs[index];
        final isActive = safeTabIndex == index;
        final isAlertTab = label == 'Alerts';
        final unread = isAlertTab ? provider.unreadAlerts : 0;

        return GestureDetector(
          onTap: () {
            setState(() => _activeTabIndex = index);
            if (isAlertTab) {
              provider.markAlertsSeen();
            }
            if (label == 'Scenarios') {
              _showWhatIfDialog(context, provider);
            }
          },
          child: Container(
            margin: const EdgeInsets.only(right: 14),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: isActive
                ? NeumorphicTheme.decoration(
                    isDark: isDark,
                    borderRadius: BorderRadius.circular(12),
                  ).copyWith(
                    color: NeumorphicColors.accent(isDark).withOpacity(0.1),
                    border: Border.all(
                      color: NeumorphicColors.accent(isDark).withOpacity(0.2),
                    ),
                  )
                : null,
            child: Row(
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                    color: isActive
                        ? NeumorphicColors.accent(isDark)
                        : NeumorphicColors.text(isDark).withOpacity(0.6),
                  ),
                ),
                if (unread > 0) ...[
                  const SizedBox(width: 6),
                  _buildBadge(unread.toString(), color: Colors.redAccent),
                ],
              ],
            ),
          ),
        );
      }),
    );
  }

  Widget _buildBadge(String text, {required Color color}) {
    return Container(
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 8,
          color: Colors.white,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildSystemMetrics(
    GlobalMetrics? metrics,
    SimulationProvider provider,
    bool isDark,
  ) {
    return Row(
      children: [
        if (metrics != null) ...[
          _buildSmallMetric(
            'Throughput',
            '${metrics.throughput.toStringAsFixed(1)}/hr',
            isDark,
          ),
          _buildDivider(isDark),
          _buildSmallMetric(
            'OEE',
            '${(metrics.oee * 100).toStringAsFixed(1)}%',
            isDark,
          ),
          _buildDivider(isDark),
          _buildSmallMetric(
            'Energy',
            '${metrics.totalEnergy.toStringAsFixed(0)} kWh',
            isDark,
            icon: Icons.bolt,
            color: Colors.yellowAccent,
          ),
          _buildSmallMetric(
            'CO2',
            '${metrics.totalCarbon.toStringAsFixed(1)} kg',
            isDark,
            icon: Icons.co2,
            color: Colors.greenAccent,
          ),
          _buildDivider(isDark),
        ],
        Text(
          provider.isSimulating ? 'RUNNING' : 'PAUSED',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w900,
            color: provider.isSimulating ? Colors.orange : Colors.grey,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          '${metrics?.environmentTime.toStringAsFixed(1) ?? '0.0'}s',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: NeumorphicColors.text(isDark),
          ),
        ),
      ],
    );
  }

  Widget _buildSmallMetric(
    String label,
    String value,
    bool isDark, {
    IconData? icon,
    Color? color,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 10, color: color ?? NeumorphicColors.accent(isDark)),
                const SizedBox(width: 4),
              ],
              Text(
                label,
                style: TextStyle(
                  fontSize: 8,
                  color: NeumorphicColors.text(isDark).withOpacity(0.5),
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 11,
              color: NeumorphicColors.text(isDark),
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDivider(bool isDark) {
    return Container(
      width: 1,
      height: 16,
      color: NeumorphicColors.darkShadow(isDark).withOpacity(0.2),
      margin: const EdgeInsets.symmetric(horizontal: 4),
    );
  }

  Widget _buildActiveTabContent(
    SimulationProvider provider,
    bool isDark,
    int safeTabIndex,
  ) {
    if (_tabs[safeTabIndex] == 'Alerts') {
      return _LiveFeedList(
        items: provider.alertsFeed,
        isDark: isDark,
        emptyText: 'No alerts yet. System is stable.',
      );
    }
    if (_tabs[safeTabIndex] == 'Logs') {
      return _LiveFeedList(
        items: provider.logsFeed,
        isDark: isDark,
        emptyText: 'No system logs yet.',
      );
    }
    if (_tabs[safeTabIndex] == 'Events') {
      return _LiveFeedList(
        items: provider.eventsFeed,
        isDark: isDark,
        emptyText: 'No routed events yet.',
      );
    }
    return Center(
      child: Text(
        'Use Scenarios tab to run What-If optimization.',
        style: TextStyle(color: NeumorphicColors.text(isDark).withOpacity(0.7)),
      ),
    );
  }

  void _showWhatIfDialog(BuildContext context, SimulationProvider provider) {
    showDialog(
      context: context,
      builder: (context) {
        String selectedScenario = 'failure_machine';
        double lookahead = 600.0;
        bool loading = false;

        return StatefulBuilder(
          builder: (context, setDialogState) {
            final isDark = Provider.of<LayoutProvider>(
              context,
              listen: false,
            ).isDarkMode;
            return AlertDialog(
              title: Text(
                'Digital Twin "What-If" Projection',
                style: TextStyle(color: NeumorphicColors.accent(isDark)),
              ),
              backgroundColor: NeumorphicColors.background(isDark),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Run branching scenarios and test optimization policies.',
                    style: TextStyle(
                      fontSize: 12,
                      color: NeumorphicColors.text(isDark).withOpacity(0.8),
                    ),
                  ),
                  const SizedBox(height: 16),
                  DropdownButton<String>(
                    value: selectedScenario,
                    items: const [
                      DropdownMenuItem(
                        value: 'failure_machine',
                        child: Text('Simulate Machine-1 Failure'),
                      ),
                      DropdownMenuItem(
                        value: 'high_demand',
                        child: Text('Increase Demand by 2x'),
                      ),
                      DropdownMenuItem(
                        value: 'bottleneck_bypass',
                        child: Text('Speed Up Machine-1'),
                      ),
                    ],
                    onChanged: (v) =>
                        setDialogState(() => selectedScenario = v!),
                  ),
                  const SizedBox(height: 16),
                  Slider(
                    value: lookahead,
                    min: 60,
                    max: 3600,
                    divisions: 10,
                    label: '${(lookahead / 60).round()}m lookahead',
                    onChanged: (v) => setDialogState(() => lookahead = v),
                  ),
                ],
              ),
              actions: [
                if (loading)
                  const CircularProgressIndicator()
                else ...[
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton(
                    onPressed: () async {
                      setDialogState(() => loading = true);
                      final actions = switch (selectedScenario) {
                        'failure_machine' => {
                          'name': 'Machine Failure',
                          'actions': [
                            {'type': 'fail_machine', 'target': 'machine-1'},
                          ],
                        },
                        'high_demand' => {
                          'name': 'High Demand',
                          'actions': [
                            {'type': 'change_demand', 'value': 0.3},
                          ],
                        },
                        'bottleneck_bypass' => {
                          'name': 'Speed Up Machine-1',
                          'actions': [
                            {
                              'type': 'speed_up',
                              'target': 'machine-1',
                              'multiplier': 0.75,
                            },
                          ],
                        },
                        _ => {'actions': <Map<String, dynamic>>[]},
                      };

                      final result = await provider.runWhatIf(
                        actions,
                        lookahead,
                      );
                      if (!context.mounted) return;
                      setDialogState(() => loading = false);
                      if (result != null) {
                        Navigator.of(context, rootNavigator: true).pop();
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          _showResults(context, result);
                        });
                      }
                    },
                    child: const Text('Run Projection'),
                  ),
                ],
              ],
            );
          },
        );
      },
    );
  }

  void _showResults(BuildContext context, Map<String, dynamic> result) {
    final isDark = Provider.of<LayoutProvider>(
      context,
      listen: false,
    ).isDarkMode;
    final policy = (result['recommended_policy'] ?? 'weighted_cost').toString();
    final policyLabel = (result['recommended_policy_label'] ?? 'PdM-Priority')
        .toString();

    showDialog(
      context: context,
      builder: (context) {
        final layout = Provider.of<LayoutProvider>(context, listen: false);
        final simulation = Provider.of<SimulationProvider>(
          context,
          listen: false,
        );

        return AlertDialog(
          backgroundColor: NeumorphicColors.background(isDark),
          title: const Text(
            'Simulation Results',
            style: TextStyle(color: Colors.green),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Projected Throughput: ${result['projected_throughput']} jobs',
                style: TextStyle(color: NeumorphicColors.text(isDark)),
              ),
              const SizedBox(height: 8),
              Text(
                'Predicted Bottlenecks: ${(result['predicted_bottlenecks'] as List<dynamic>? ?? []).join(', ')}',
                style: TextStyle(color: NeumorphicColors.text(isDark)),
              ),
              const SizedBox(height: 12),
              Text(
                'Best Policy: $policyLabel ($policy)',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: NeumorphicColors.accent(isDark),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                (result['recommendation'] ??
                        'Apply optimization to reduce predicted bottlenecks.')
                    .toString(),
                style: TextStyle(
                  fontStyle: FontStyle.italic,
                  color: NeumorphicColors.text(isDark).withOpacity(0.7),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(
                'Cancel',
                style: TextStyle(color: NeumorphicColors.text(isDark)),
              ),
            ),
            ElevatedButton(
              onPressed: () async {
                final ok = await simulation.applyOptimizationPolicy(policy);
                if (!context.mounted) return;
                if (ok) {
                  layout.pulseConveyorGlow();
                  Navigator.of(context, rootNavigator: true).pop();
                }
              },
              child: const Text('Apply Optimization'),
            ),
          ],
        );
      },
    );
  }
}

class _LiveFeedList extends StatefulWidget {
  final List<Map<String, dynamic>> items;
  final bool isDark;
  final String emptyText;

  const _LiveFeedList({
    required this.items,
    required this.isDark,
    required this.emptyText,
  });

  @override
  State<_LiveFeedList> createState() => _LiveFeedListState();
}

class _LiveFeedListState extends State<_LiveFeedList> {
  final ScrollController _controller = ScrollController();

  @override
  void didUpdateWidget(covariant _LiveFeedList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.items.length != oldWidget.items.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!_controller.hasClients) return;
        _controller.animateTo(
          _controller.position.maxScrollExtent,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
        );
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.items.isEmpty) {
      return Center(
        child: Text(
          widget.emptyText,
          style: TextStyle(
            color: NeumorphicColors.text(widget.isDark).withOpacity(0.6),
          ),
        ),
      );
    }

    return ListView.separated(
      controller: _controller,
      itemCount: widget.items.length,
      separatorBuilder: (_, __) => Divider(
        color: NeumorphicColors.darkShadow(widget.isDark).withOpacity(0.2),
        height: 1,
      ),
      itemBuilder: (context, index) {
        final item = widget.items[index];
        final eventType = (item['event_type'] ?? 'EVENT').toString();
        final message = (item['message'] ?? eventType).toString();
        final timestamp = (item['timestamp'] ?? '').toString();

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
          child: Row(
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _eventColor(eventType),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      eventType,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: NeumorphicColors.accent(widget.isDark),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      message,
                      style: TextStyle(
                        fontSize: 11,
                        color: NeumorphicColors.text(widget.isDark),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Text(
                _shortTime(timestamp),
                style: TextStyle(
                  fontSize: 10,
                  color: NeumorphicColors.text(widget.isDark).withOpacity(0.5),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  String _shortTime(String raw) {
    if (raw.isEmpty) return '--:--:--';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) {
      return raw;
    }
    final hh = parsed.hour.toString().padLeft(2, '0');
    final mm = parsed.minute.toString().padLeft(2, '0');
    final ss = parsed.second.toString().padLeft(2, '0');
    return '$hh:$mm:$ss';
  }

  Color _eventColor(String type) {
    if (type.contains('FAILURE') || type.contains('HIGH'))
      return Colors.redAccent;
    if (type.contains('MAINTENANCE')) return Colors.orangeAccent;
    if (type.contains('ROUTING')) return Colors.cyanAccent;
    return Colors.greenAccent;
  }
}
