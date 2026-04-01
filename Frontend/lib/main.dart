import 'package:flutter/material.dart';
import 'package:frontend/layout/main_layout.dart';
import 'package:frontend/screens/dashboard_screen.dart';
import 'package:frontend/theme/app_theme.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Digital Twin Dashboard',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const MyHomePage(title: 'Digital Twin Controls'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  int _selectedIndex = 0;
  bool _isSimulating = false;

  @override
  Widget build(BuildContext context) {
    return MainLayout(
      selectedIndex: _selectedIndex,
      onItemSelected: (index) {
        setState(() {
          _selectedIndex = index;
        });
      },
      isSimulationRunning: _isSimulating,
      onStartSimulation: () {
        setState(() {
          _isSimulating = !_isSimulating;
        });
      },
      onSettings: () {},
      onProfile: () {},
      child: const DashboardScreen(),
    );
  }
}
