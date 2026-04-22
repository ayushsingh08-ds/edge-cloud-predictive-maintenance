import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'providers/layout_provider.dart';
import 'providers/simulation_provider.dart';
import 'screens/layout_editor_screen.dart';
import 'screens/dashboard_3d_screen.dart';
import 'components/neumorphic_theme.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => LayoutProvider()),
        ChangeNotifierProvider(create: (_) => SimulationProvider()),
      ],
      child: const SmartFactoryApp(),
    ),
  );
}

class SmartFactoryApp extends StatelessWidget {
  const SmartFactoryApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final layout = Provider.of<LayoutProvider>(context);
    return MaterialApp(
      title: 'Smart Factory Layout Editor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        textTheme: GoogleFonts.outfitTextTheme(),
        scaffoldBackgroundColor: NeumorphicColors.background(layout.isDarkMode),
        colorScheme: ColorScheme.fromSeed(
          seedColor: NeumorphicColors.accent(layout.isDarkMode),
          surface: NeumorphicColors.background(layout.isDarkMode),
          brightness: layout.isDarkMode ? Brightness.dark : Brightness.light,
        ),
      ),
      builder: (context, child) {
        return ExcludeSemantics(
          excluding: true,
          child: child!,
        );
      },
      home: Consumer<LayoutProvider>(
        builder: (context, layout, _) {
          return layout.show3D ? const Dashboard3DScreen() : const LayoutEditorScreen();
        },
      ),
    );
  }
}
