import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../providers/layout_provider.dart';
import 'neumorphic_theme.dart';

class FactorySidebar extends StatelessWidget {
  const FactorySidebar({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 100,
      decoration: NeumorphicTheme.decoration(
        borderRadius: const BorderRadius.horizontal(right: Radius.circular(24)),
      ),
      child: Column(
        children: [
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24.0),
            child: Icon(Icons.hub, color: NeumorphicColors.accent, size: 32),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: LayoutNodeType.values.map((type) {
                return DraggableComponent(type: type);
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class DraggableComponent extends StatelessWidget {
  final LayoutNodeType type;
  const DraggableComponent({required this.type, Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12.0),
      child: Draggable<LayoutNodeType>(
        data: type,
        feedback: Material(
          color: Colors.transparent,
          child: Container(
            width: 70,
            height: 70,
            decoration: NeumorphicTheme.decoration(borderRadius: BorderRadius.circular(12)).copyWith(
              boxShadow: NeumorphicTheme.elevatedShadows(blurRadius: 15),
            ),
            child: Icon(_getIconForType(type), color: NeumorphicColors.accent, size: 24),
          ),
        ),
        child: NeumorphicButton(
          padding: 8,
          borderRadius: 12,
          onPressed: () {
            Provider.of<LayoutProvider>(context, listen: false).addNode(type, const Offset(100, 100));
          },
          child: Column(
            children: [
              Icon(_getIconForType(type), color: NeumorphicColors.accent, size: 24),
              const SizedBox(height: 4),
              Text(
                type.value,
                style: const TextStyle(fontSize: 10, color: NeumorphicColors.text),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getIconForType(LayoutNodeType type) {
    switch (type) {
      case LayoutNodeType.machine: return Icons.settings_suggest;
      case LayoutNodeType.buffer: return Icons.inventory_2;
      case LayoutNodeType.source: return Icons.login;
      case LayoutNodeType.sink: return Icons.logout;
      case LayoutNodeType.divider: return Icons.alt_route;
      case LayoutNodeType.conveyor: return Icons.sync_alt;
    }
  }
}

class PropertiesPanel extends StatefulWidget {
  const PropertiesPanel({Key? key}) : super(key: key);

  @override
  _PropertiesPanelState createState() => _PropertiesPanelState();
}

class _PropertiesPanelState extends State<PropertiesPanel> {
  final Map<String, TextEditingController> _controllers = {};

  @override
  void dispose() {
    for (var c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<LayoutProvider>(context);
    final node = provider.selectedNode;

    if (node == null) {
      return Container(
        width: 300,
        padding: const EdgeInsets.all(24),
        decoration: NeumorphicTheme.decoration(
          borderRadius: const BorderRadius.horizontal(left: Radius.circular(24)),
        ),
        child: const Center(
          child: Text(
            'Select a component to edit its properties',
            style: TextStyle(fontStyle: FontStyle.italic, color: NeumorphicColors.text, fontSize: 13),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return Container(
      width: 300,
      decoration: NeumorphicTheme.decoration(
        borderRadius: const BorderRadius.horizontal(left: Radius.circular(24)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildHeader(provider, node),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              children: [
                _buildSectionHeader('General Info'),
                _buildReadOnlyField('ID', node.id),
                _buildReadOnlyField('Type', node.type.value),
                const SizedBox(height: 16),
                _buildSectionHeader('Configuration'),
                ...node.properties.entries.map((entry) {
                  return _buildPropertyField(provider, node.id, entry.key, entry.value);
                }).toList(),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(LayoutProvider provider, LayoutNode node) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 12, 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Icon(_getIconForType(node.type), size: 18, color: NeumorphicColors.accent),
              const SizedBox(width: 10),
              Text(
                'Component Editor',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: NeumorphicColors.accent),
              ),
            ],
          ),
          IconButton(
            onPressed: () => provider.removeSelectedNode(),
            icon: const Icon(Icons.delete_sweep, color: Colors.redAccent, size: 20),
            tooltip: 'Remove Component',
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: NeumorphicColors.accent, letterSpacing: 1.2),
      ),
    );
  }

  Widget _buildReadOnlyField(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: NeumorphicColors.text)),
          Text(value, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: NeumorphicColors.text)),
        ],
      ),
    );
  }

  Widget _buildPropertyField(LayoutProvider provider, String nodeId, String key, dynamic value) {
    final controllerKey = '$nodeId-$key';
    if (!_controllers.containsKey(controllerKey)) {
      _controllers[controllerKey] = TextEditingController(text: value.toString());
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            key.replaceAll('_', ' ').toUpperCase(),
            style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: NeumorphicColors.text),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _controllers[controllerKey],
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: NeumorphicColors.accent),
            onSubmitted: (text) {
              final newValue = double.tryParse(text) ?? text;
              final newProps = Map<String, dynamic>.from(provider.selectedNode!.properties);
              newProps[key] = newValue;
              provider.updateNodeProperties(nodeId, newProps);
            },
            decoration: InputDecoration(
              isDense: true,
              filled: true,
              fillColor: Colors.white24,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: NeumorphicColors.accent, width: 1.5),
              ),
            ),
          ),
        ],
      ),
    );
  }

  IconData _getIconForType(LayoutNodeType type) {
    switch (type) {
      case LayoutNodeType.machine: return Icons.settings_suggest;
      case LayoutNodeType.buffer: return Icons.inventory_2;
      case LayoutNodeType.source: return Icons.login;
      case LayoutNodeType.sink: return Icons.logout;
      case LayoutNodeType.divider: return Icons.alt_route;
      case LayoutNodeType.conveyor: return Icons.sync_alt;
    }
  }
}
