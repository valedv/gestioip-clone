#!/usr/bin/perl -w


# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# ip_update_gestioip_dns.pl Version 2.2.8.1

# script para actualizar la BBDD del sistema GestioIP against the DNS

# This scripts synchronizes only the networks of GestioIP with marked "sync"-field
# see documentation for further information (www.gestioip.net)


# Usage: ./ip_update_gestioip_dns.pl --help

# execute it from cron. Example crontab:
# 30 10 * * * /usr/share/gestioip/bin/ip_update_gestioip_dns.pl -o -m > /dev/null 2>&1


use strict;
use Getopt::Long;
Getopt::Long::Configure ("no_ignore_case");
use DBI;
use Time::Local;
use Time::HiRes qw(sleep);
use Date::Calc qw(Add_Delta_Days); 
use Date::Manip qw(UnixDate);
use Net::IP;
use Net::IP qw(:PROC);
use Net::Ping::External qw(ping);
use Mail::Mailer;
use Socket;
use Parallel::ForkManager;
use FindBin qw($Bin);
use Fcntl qw(:flock);
use Net::DNS;


my $VERSION="2.2.8.0";

	 
my $dir = $Bin;

$dir =~ /^(.*)\/bin/;
my $base_dir=$1;


my $config_name="ip_update_gestioip.conf";

# my $dir = "/apsolute/path/to/$config_name";

if ( ! -r "${base_dir}/etc/${config_name}" ) {
	print "\nCan't find configuration file \"$config_name\"\n";
	print "\n\"$dir/$config_name\" doesn't exists\n";
	exit 1;
}

my $conf = $base_dir . "/etc/" . $config_name;


my ( $disable_audit, $test, $verbose, $log, $mail, $help, $version_arg );

GetOptions(
	"verbose!"=>\$verbose,
	"Version!"=>\$version_arg,
	"test!"=>\$test,
	"log=s"=>\$log,
	"disable_audit!"=>\$disable_audit,
	"mail!"=>\$mail,
	"help!"=>\$help
) or print_help();

my $enable_audit = "1";
$enable_audit = "0" if $test || $disable_audit;

if ( $help ) { print_help(); }
if ( $version_arg ) { print_version(); }
if ( $test && ! $verbose ) { print_help(); }

my %params;

open(VARS,"<$conf") or die "Can not open $conf: $!\n";
while (<VARS>) {
	chomp;
	s/#.*//;
	s/^\s+//;
	s/\s+$//;
	next unless length;
	my ($var, $value) = split(/\s*=\s*/, $_, 2);
	$params{$var} = $value;
}
close VARS;

my $lang=$params{lang} || "en";
my $vars_file=$base_dir . "/etc/vars/vars_update_gestioip_" . "$lang";

my $gip_version=get_version();

if ( $VERSION !~ /$gip_version/ ) {
	print "Script and GestioIP version are not compatible\n\nGestioIP version: $gip_version - script version: $VERSION\n\n";
	exit;
}

my %lang_vars;

open(LANGVARS,"<$vars_file") or die "Can no open $vars_file: $!\n";
while (<LANGVARS>) {
	chomp;
	s/#.*//;
	s/^\s+//;
	s/\s+$//;
	next unless length;
	my ($var, $value) = split(/\s*=\s*/, $_, 2);
	$lang_vars{$var} = $value;
}
close LANGVARS;


if ( $params{pass_gestioip} !~ /.+/ ) {
	print  "\nERROR\n\n$lang_vars{no_pass_message} $conf)\n\n";
	exit 1;
}


my $client_name_conf = $params{client};
my $client_count = count_clients();
my $client_id;
if ( $client_count == "1" ) {
	my $one_client_name = check_one_client_name("$client_name_conf") || "";
	if ( $one_client_name eq $client_name_conf || $client_name_conf eq "DEFAULT" ) {
		$client_id=get_client_id_one() || "";
	}
} else {
	$client_id=get_client_id_from_name("$client_name_conf") || "";
}

if ( ! $client_id ) {
	print "$client_name_conf: $lang_vars{client_not_found_message} $conf\n";
	exit 1;
}

my $lockfile = $base_dir . "/var/run/" . $client_name_conf . "_ip_update_gestioip_dns.lock";

no strict 'refs';
open($lockfile, '<', $0) or die("Unable to create lock file: $!\n");
use strict;

unless (flock($lockfile, LOCK_EX|LOCK_NB)) {
	print "$0 is already running. Exiting.\n";
	exit(1);
}



my $logfile_name;
if ( $client_count == "1" ) {
	$logfile_name = "ip_update_gestioip_dns.log";
} else {
	$logfile_name = $client_name_conf . "_ip_update_gestioip_dns.log";
}

my $logdir="$params{logdir}" if ( ! $log );

if ( ! -d $logdir ) {
	print "$lang_vars{logdir_not_found_message}: $logdir - using $log\n";
	$log=$base_dir . "/var/log/" . $logfile_name;
} else {
	$log=$logdir . "/" . $logfile_name;
}

my $generic_dyn_host_name=$params{'generic_dyn_host_name'};
$generic_dyn_host_name =~ s/,/|/g;

my $mail_destinatarios = \$params{mail_destinatarios};
my $mail_from = \$params{mail_from};

my ($s, $mm, $h, $d, $m, $y) = (localtime) [0,1,2,3,4,5];
$m++;
$y+=1900;
if ( $d =~ /^\d$/ ) { $d = "0$d"; }
if ( $s =~ /^\d$/ ) { $s = "0$s"; }
if ( $m =~ /^\d$/ ) { $m = "0$m"; }
if ( $mm =~ /^\d$/ ) { $mm = "0$mm"; }
my $mydatetime = "$y-$m-$d $h:$mm:$s";



open(LOG,">$log") or die "$log: $!\n";


my $count_entradas_dns=0;
my $count_entradas_dns_timeout=0;

print LOG "\n######## Synchronization against DNS ($mydatetime) ########\n\n";
if ( $test ) {
	print LOG "\n--- $lang_vars{test_mod_message} ---\n";
	print "\n--- $lang_vars{test_mod_message} ---\n";
}

my @vigilada_redes=get_vigilada_redes("$client_id");

if ( ! $vigilada_redes[0] ) {
	print "\n--- $lang_vars{no_sync_redes} ---\n\n";
	print "\n$lang_vars{mark_red_message}\n";
	print "\n$lang_vars{mark_red_explic_message}\n\n";
	exit 1;
}

my @values_ignorar;
if ( $params{'ignorar'} ) {
	@values_ignorar=split(",",$params{'ignorar'});
} else {
	$values_ignorar[0]="__IGNORAR__";
}


if ( $vigilada_redes[0]->[1] ) {
	my $audit_type="23";
	my $audit_class="2";
	my $update_type_audit="4";
	my $event="---";
	insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
}


my @client_entries=get_client_entries("$client_id");
my $default_resolver = $client_entries[0]->[20];
my @dns_servers =("$client_entries[0]->[21]","$client_entries[0]->[22]","$client_entries[0]->[23]");


my $l=0;
foreach (@vigilada_redes) {

	my $red_num="$vigilada_redes[$l]->[2]";

	print "\n$vigilada_redes[$l]->[0]/$vigilada_redes[$l]->[1]\n" if $verbose;

	if ( $params{dyn_rangos_only} eq "yes" ) {
		print "\n($lang_vars{sync_only_rangos_message})\n\n" if $verbose;
		print LOG "\n($lang_vars{sync_only_rangos_message})\n\n" if $verbose;
	} else {
		print "\n";
	}

	my @values_redes = ();
	my @reserved_ranges_found = ();
	if ( $params{dyn_rangos_only} eq "yes" ) {
		 @reserved_ranges_found=check_for_reserved_range("$client_id","$red_num");
	}

	if ( ! $reserved_ranges_found[0] && $params{dyn_rangos_only} eq "yes" ) {
		print "$lang_vars{no_range_message}\n\n";
		$l++;
		next;
	}

	@values_redes = get_red("$client_id","$red_num");

	if ( ! $values_redes[0] ) {
		print "$lang_vars{algo_malo_message}\n";
		print LOG "$lang_vars{algo_malo_message}\n";
	}

	my $red = "$values_redes[0]->[0]" || "";
	my $BM = "$values_redes[0]->[1]" || "";
	my $descr = "$values_redes[0]->[2]" || "";
	my $loc_id = "$values_redes[0]->[3]" || "";
	my $redob = "$red/$BM";
	my $host_loc = get_loc_from_redid("$client_id","$red_num");
	$host_loc = "---" if $host_loc eq "NULL";
	my $host_cat = "---";

	my $ipob = new Net::IP ($redob) or print "error: $lang_vars{comprueba_red_BM_message}: $red/$BM\n";
	my $redint=($ipob->intip());
	my $first_ip_int = $redint + 1;
	my $last_ip_int = ($ipob->last_int());
	$last_ip_int = $last_ip_int - 1;


        #check if DNS servers are alive

	my $res_dns;
	my $dns_error = "";

	if ( $default_resolver eq "yes" ) {
		$res_dns = Net::DNS::Resolver->new(
		retry       => 2,
		udp_timeout => 5,
		recurse     => 1,
		debug       => 0,
                );
	} else {
		$res_dns = Net::DNS::Resolver->new(
		retry       => 2,
		udp_timeout => 5,
		nameservers => [@dns_servers],
		recurse     => 1,
		debug       => 0,
		);
	}

	my $test_ip_int=$first_ip_int;
	my $test_ip=int_to_ip("$test_ip_int");

	my $ptr_query=$res_dns->query("$test_ip");

	if ( ! $ptr_query) {
		if ( $res_dns->errorstring eq "query timed out" ) {
			print LOG "$lang_vars{no_dns_server_message} (1): " . $res_dns->errorstring . "\n\n";
			print "$lang_vars{no_dns_server_message} (1): " . $res_dns->errorstring . "\n\n" if $verbose;
			$l++;
			next;
		}
	}

	my $used_nameservers = $res_dns->nameservers;

	my $all_used_nameservers = join (" ",$res_dns->nameserver());

	if ( $used_nameservers eq "0" ) {
		print LOG "$lang_vars{no_dns_server_message} (2)\n\n";
		print "$lang_vars{no_dns_server_message} (2)\n\n" if $verbose;
		$l++;
		next;
	}

	if ( $all_used_nameservers eq "127.0.0.1" && $default_resolver eq "yes" ) {
		print LOG "$lang_vars{no_answer_from_dns_message} - $lang_vars{nameserver_localhost_message}\n\n$lang_vars{exiting_message}\n\n";
		print "$lang_vars{no_answer_from_dns_message} - $lang_vars{nameserver_localhost_message}\n\n$lang_vars{exiting_message}\n\n" if $verbose;
		$l++;
		next;
	}

	my $mydatetime = time();

	my $j=0;
	my $hostname;
	my ( $ip_int, $ip_bin, $ip_ad, $pm, $res, $pid, $ip );
	my ( %res_sub, %res, %result);

	my $MAX_PROCESSES=$params{max_sinc_procs} || "254";
	$pm = new Parallel::ForkManager($MAX_PROCESSES);

	$pm->run_on_finish(
		sub { my ($pid, $exit_code, $ident) = @_;
			$res_sub{$pid}=$exit_code;
		}
	);
	$pm->run_on_start(
		sub { my ($pid,$ident)=@_;
			$res{$pid}="$ident";
		}
	);

	for (my $i = $first_ip_int; $i <= $last_ip_int; $i++) {
		$count_entradas_dns++;
		my $exit;
		$ip_ad=int_to_ip($i);
		
			##fork
			$pid = $pm->start("$ip_ad") and next;
				#child
				my $p = ping(host => "$ip_ad", timeout => 2);
				if ( $p ) {
					$exit=0;
				} else {
					$exit=1;
				}


				my ($ptr_query,$dns_result_ip);

				if ( $default_resolver eq "yes" ) {
					$res_dns = Net::DNS::Resolver->new(
					retry       => 2,
					udp_timeout => 5,
					recurse     => 1,
					debug       => 0,
					);
				} else {
					$res_dns = Net::DNS::Resolver->new(
					retry       => 2,
					udp_timeout => 5,
					nameservers => [@dns_servers],
					recurse     => 1,
					debug       => 0,
					);
				}

				if ( $ip_ad =~ /\w+/ ) {
					$ptr_query = $res_dns->query("$ip_ad");

					if ($ptr_query) {
						foreach my $rr ($ptr_query->answer) {
							next unless $rr->type eq "PTR";
							$dns_result_ip = $rr->ptrdname;
						}
					} else {
						$dns_error = $res_dns->errorstring;
					}
				}


				if ( $dns_error =~ /(query timed out|no nameservers)/ ) {
					exit 5;
				} else {
					if ( $dns_result_ip && $exit == 0 ) {
						$exit=2;
					} elsif ( $dns_result_ip && $exit == 1 ) {
						$exit=3;
					} elsif ( ! $dns_result_ip && $exit == 0 ) {
						$exit=4;

					}
				}


				$pm->finish($exit); # Terminates the child process

	}

	$pm->wait_all_children;


	while (($pid,$ip) = each ( %res )) {
		$result{$ip}=$res_sub{$pid};
	}

	my @ip;
	my @ip_range;
	my @ip_range_new;
	my @range_ids;


	if ( $params{dyn_rangos_only} eq "yes" ) {
		@ip=get_host_range("$client_id","$first_ip_int","$last_ip_int");
		$first_ip_int = $ip[0]->[0];
		$last_ip_int = $ip[-1]->[0];
		if ( ! $first_ip_int || ! $last_ip_int ) {
			print "$lang_vars{no_range_message}\n\n";
			$l++;
			next;
		}
	} else {
		@ip=get_host("$client_id","$first_ip_int","$last_ip_int");
	}

	my $k = 0;
	for (my $i = $first_ip_int; $i <= $last_ip_int; $i++) {


		$ip_ad = int_to_ip($i);
		my $exit=$result{$ip_ad}; 

		my $hostname_bbdd;
		my $cat_id="-1";
		my $int_admin="n";
		my $utype="dns";
		my $utype_id;
		my $host_descr = "NULL";
		my $comentario = "NULL";
		my $range_id="-1";
		$range_id= $ip[$k]->[10] if $ip[$k]->[10] && $i eq $ip[$k]->[0];

		if ( defined($ip[$k]->[0]) ) {
			if ( ( $ip[$k]->[1] || $ip[$k]->[10] ne "-1" ) && $i eq $ip[$k]->[0] ) {
				$hostname_bbdd = $ip[$k]->[1];
				$host_descr = $ip[$k]->[2] if $ip[$k]->[2];
				$cat_id=get_cat_id("$ip[$k]->[4]") if $ip[$k]->[4];
				$int_admin=$ip[$k]->[5] if $ip[$k]->[5];
				$comentario = $ip[$k]->[6] if $ip[$k]->[6];
				$utype=$ip[$k]->[7] if $ip[$k]->[7];
				$utype= "---" if $utype eq "NULL"; 
				$utype_id=get_utype_id("$utype") || "-1";
				$range_id = $ip[$k]->[10] if $ip[$k]->[10];
				
			}
		}

		if ( $params{dyn_rangos_only} eq "yes" ) {
			if ( $range_id eq "-1" && $i eq $ip[$k]->[0] ) {
				$k++;
				next;
			} elsif ( $range_id eq "-1" ) {
				next;
			}
		}

		print "$ip_ad: " if $verbose; 
		print LOG "$ip_ad: "; 

		$utype_id=get_utype_id("$utype") if ! $utype_id;

		my $ping_result=0;
		$ping_result=1 if $exit == "0" || $exit == "2" || $exit == "4";

		# Ignor IP if update type has higher priority than "dns" 
		if ( $utype ne "dns" && $utype ne "---" ) {
			if ( $hostname_bbdd || $range_id ne "-1" ) {
				$k++;
			}
			if ( $hostname_bbdd ) {
				print "$hostname_bbdd - update type: $utype - $lang_vars{ignorado_message}\n" if $verbose;
				print LOG "$hostname_bbdd - update type: $utype - $lang_vars{ignorado_message}\n";
				update_host_ping_info("$client_id","$i","$ping_result") if ! $test;
			} else {
				print "update type: $utype - $lang_vars{ignorado_message}\n" if $verbose;
				print LOG "update type: $utype - $lang_vars{ignorado_message}\n";
			}
			next;
		}
			
		my $ignor_reason=0; # 1: no dns entry; 2: generic auto name; 3: hostname matches ignore-string
		my @dns_result_ip;
		my $hostname;
		if ( $exit == 2 || $exit == 3 ) {

			my ($ptr_query,$dns_result_ip);

			if ( $default_resolver eq "yes" ) {
				$res_dns = Net::DNS::Resolver->new;
			} else {

				$res_dns = Net::DNS::Resolver->new(
					nameservers => [@dns_servers],
					recurse     => 1,
					debug       => 0,
				);
			}

			$res_dns->udp_timeout(10);

			if ( $ip_ad =~ /\w+/ ) {
				$ptr_query = $res_dns->search("$ip_ad");

				if ($ptr_query) {
					foreach my $rr ($ptr_query->answer) {
						next unless $rr->type eq "PTR";
						$dns_result_ip = $rr->ptrdname;
					}
				} else {
					$dns_error = $res_dns->errorstring;
				}
			}


			$hostname = $dns_result_ip || "unknown";

			if ( $hostname eq "unknown" ) {
				$count_entradas_dns_timeout++;
				$ignor_reason=1;
			}
		} else {
			$hostname = "unknown";
			$ignor_reason=1;
		}


		my $ptr_name = $ip_ad;
		$ptr_name =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
#		my $generic_auto = "$2-$3-$4|$4-$3-$2";
		my $generic_auto = "$2-$3-$4|$4-$3-$2|$1-$2-$3|$3-$2-$1";

		my $igno_name;
		my $igno_set = 0;

		if ( $hostname =~ /$generic_auto/ && $params{ignore_generic_auto} eq "yes" ) {
			$igno_set = 1;
			$hostname="unknown";
			$igno_name="$generic_auto";
			$ignor_reason=2;
		}

		foreach (@values_ignorar) {
			if ( $hostname =~ /$_/ ) {
				$igno_set = 1;
				$hostname="unknown";
				$igno_name="$_";
				$ignor_reason=3;
			}
			next;
		}

		if ( $hostname =~ /$generic_dyn_host_name/ ) {
			$igno_set = 1;
			$hostname="unknown";
			$igno_name="$generic_dyn_host_name";
			$ignor_reason=4;
		}


		if ( $hostname_bbdd ) {

			if ( $hostname_bbdd eq $hostname && $hostname ne "unknown" && $igno_set == "0") {
				print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n" if $verbose;
				print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n";
				update_host_ping_info("$client_id","$i","$ping_result") if ! $test;

			} else {
				if ( $params{delete_dns_hosts_down_all} eq "yes" && $hostname eq "unknown" && $hostname_bbdd !~ /$generic_dyn_host_name/ && $ping_result == "0" ) {
					if ( $range_id eq "-1" ) {
						my $host_id=get_host_id_from_ip_int("$client_id","$i");
						delete_custom_host_column_entry("$client_id","$host_id");
						delete_ip("$client_id","$i","$i") if ! $test;
					} else {
						my $host_id=get_host_id_from_ip_int("$client_id","$i");
						delete_custom_host_column_entry("$client_id","$host_id");
						clear_ip("$client_id","$i","$i") if ! $test;
					}
					# no dns entry
					if ( $ignor_reason == "1" ) {
						print "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{no_dns_message} + $lang_vars{no_ping_message})\n" if $verbose;
						print LOG "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{no_dns_message} + $lang_vars{no_ping_message})\n";
					# hostname matches generic man auto name
					} elsif ( $ignor_reason == "2" ) {
						print "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{auto_generic_name_message} + $lang_vars{no_ping_message})\n" if $verbose;
						print LOG "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{auto_generic_name_message} + $lang_vars{no_ping_message})\n";
					# hostname matches ignore-string
					} elsif ( $ignor_reason == "3" ) {
						print "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{tiene_man_string_no_ping_message})\n" if $verbose;
						print LOG "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{tiene_man_string_no_ping_message})\n";
					} else {
						print "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{no_ping_message})\n" if $verbose;
						print LOG "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{no_ping_message})\n";
					}
					$k++;
					my $audit_type="14";
					my $audit_class="1";
					my $update_type_audit="4";
					my $host_descr_audit = $host_descr;
					$host_descr_audit = "---" if $host_descr_audit eq "NULL";
					my $comentario_audit = $comentario;
					$comentario_audit = "---" if $comentario_audit eq "NULL";
					my $event="$ip_ad,$hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
					insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
					next;
				} elsif ( $hostname eq "unknown" && $hostname_bbdd =~ /$generic_dyn_host_name/ && $ping_result == "0" ) {
					if ( $range_id eq "-1" ) {
						my $host_id=get_host_id_from_ip_int("$client_id","$i");
						delete_custom_host_column_entry("$client_id","$host_id");
						delete_ip("$client_id","$i","$i") if ! $test;
					} else {
						my $host_id=get_host_id_from_ip_int("$client_id","$i");
						delete_custom_host_column_entry("$client_id","$host_id");
						clear_ip("$client_id","$i","$i") if ! $test;
					}
					print "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{generic_dyn_host_message} + $lang_vars{no_ping_message})\n" if $verbose;
					print LOG "$lang_vars{entrada_borrado_message}: $hostname_bbdd ($lang_vars{generic_dyn_host_message} + $lang_vars{no_ping_message})\n";
					$k++;
					my $audit_type="14";
					my $audit_class="1";
					my $update_type_audit="4";
					my $host_descr_audit = $host_descr;
					$host_descr_audit = "---" if $host_descr_audit eq "NULL";
					my $comentario_audit = $comentario;
					$comentario_audit = "---" if $comentario_audit eq "NULL";
					my $event="$ip_ad,$hostname_bbdd,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
					insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
					next;
				} elsif ( $hostname eq "unknown" && $ping_result == "1" ) {
					# no dns entry
					if ( $ignor_reason == "1" ) {
						print "$lang_vars{tiene_entrada_message}: $hostname_bbdd ($lang_vars{no_dns_message}) - $lang_vars{ignorado_message}\n" if $verbose;
						print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd ($lang_vars{no_dns_message}) - $lang_vars{ignorado_message}\n";
					# generic auto name
					} elsif ( $ignor_reason == "2" ) {
						print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n" if $verbose;
						print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n";
					# hostname matches ignore-string
					} elsif ( $ignor_reason == "3" ) {
						print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n" if $verbose;
						print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n";
					# hostname matches generic-dynamic name
					} elsif ( $ignor_reason == "4" ) {
						print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}<br>\n";
					}
 
					update_host_ping_info("$client_id","$i","$ping_result") if ! $test;
					$k++;
					next;
				}

				if ( $hostname_bbdd ne $hostname ) {
#				if ( $hostname_bbdd ne $hostname  && $hostname_bbdd ne "unknown" ) {
#					print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n" if $verbose;
#					print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n";
#				} elsif ( $hostname_bbdd ne $hostname ) {
						update_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result") if ! $test;
						print "$lang_vars{entrada_actualizada_message}: $hostname ($lang_vars{entrada_antigua_message}: $hostname_bbdd)\n" if $verbose;
						print LOG "$lang_vars{entrada_actualizada_message}: $hostname ($lang_vars{entrada_antigua_message}: $hostname_bbdd)\n";

					my $audit_type="1";
					my $audit_class="1";
					my $update_type_audit="4";
					my $host_descr_audit = $host_descr;
					$host_descr_audit = "---" if $host_descr_audit eq "NULL";
					my $comentario_audit = $comentario;
					$comentario_audit = "---" if $comentario_audit eq "NULL";
					my $event="$ip_ad,$hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
					insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";

				} elsif ( $ping_result == 1 && $hostname_bbdd eq "unknown" && $hostname eq "unknown" ) {
					print "$lang_vars{tiene_entrada_message}: $hostname_bbdd - ($lang_vars{generico_message}) $lang_vars{ignorado_message}\n" if $verbose;
					print LOG "$lang_vars{tiene_entrada_message}: $hostname_bbdd - $lang_vars{ignorado_message}\n";
					update_host_ping_info("$client_id","$i","$ping_result") if ! $test;

				} else {
					update_host_ping_info("$client_id","$i","$ping_result") if ! $test;
					print "$hostname_bbdd: $lang_vars{entrada_cambiado_message} (DNS: $hostname) - $lang_vars{ignorado_message} ($lang_vars{update_type_message}: $utype)\n" if $verbose;
					print LOG "$hostname_bbdd: $lang_vars{entrada_cambiado_message} (DNS: $hostname) - $lang_vars{ignorado_message} ($lang_vars{update_type_message}: $utype)\n";
				}
			}
			$k++;
			next;
		}

		# no hostname_bbdd; 2: dns ok, ping ok; 3: dns ok, ping failed, 4: DNS not ok, ping OK
		if ( $exit eq 2 || $exit eq 3 || $exit eq 4 ) {
			if ( $exit eq 3 && $hostname eq "unknown" && $igno_set == "1" ) {
				if ( $ignor_reason == "2" ) {
					print "$lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
					print LOG "$lang_vars{tiene_string_no_ping_message} - $lang_vars{ignorado_message}\n";
				} else {
					print "$lang_vars{tiene_man_string_no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
					print LOG "$lang_vars{tiene_man_string_no_ping_message} - $lang_vars{ignorado_message}\n";
				}
				if ( $range_id ne "-1" ) {
					$k++;
				}
				next;
			}
			if ( $range_id eq "-1" ) {
				insert_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result") if ! $test;
			} else {
				update_ip_mod("$client_id","$i","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$ping_result") if ! $test;
				$k++;
			}
			if ( $exit eq 2 && $hostname eq "unknown" && $igno_set == "1") {
				if ( $ignor_reason == "2" ) {
					print "$lang_vars{auto_generic_name_message} - $lang_vars{host_anadido_message}: unknown\n" if $verbose;
					print LOG "$lang_vars{auto_generic_name_message} - $lang_vars{host_anadido_message}: unknown\n";
				} else {
					print "$lang_vars{generic_dyn_host_message} - $lang_vars{host_anadido_message}: unknown\n" if $verbose;
					print LOG "$lang_vars{generic_dyn_host_message} - $lang_vars{host_anadido_message}: unknown\n";
				}
			} else {
				print "$lang_vars{host_anadido_message}: $hostname\n" if $verbose;
				print LOG "$lang_vars{host_anadido_message}: $hostname\n";
			}
			my $audit_type="15";
			my $audit_class="1";
			my $update_type_audit="4";
			my $host_descr_audit = $host_descr;
			$host_descr_audit = "---" if $host_descr_audit eq "NULL";
			my $comentario_audit = $comentario;
			$comentario_audit = "---" if $comentario_audit eq "NULL";
			my $event="$ip_ad,$hostname,$host_descr_audit,$host_loc,$host_cat,$comentario_audit";
			insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
		} else {
			print "$lang_vars{no_dns_message} + $lang_vars{no_ping_message} - $lang_vars{ignorado_message}\n" if $verbose;
			print LOG "$lang_vars{no_dns_message} + $lang_vars{no_ping_message} - $lang_vars{ignorado_message}\n";
			if ( $range_id ne "-1" ) {
				$k++;
			}
		} 
	}
$l++;
}

close LOG;

$count_entradas_dns ||= "0";


my $count_entradas = $count_entradas_dns;

send_mail() if $mail;


#######################
# Subroutiens
#######################

sub get_vigilada_redes {
	my ( $client_id,$red ) = @_;
	my $ip_ref;
	my @vigilada_redes;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT red, BM, red_num, loc FROM net WHERE vigilada=\"y\" AND client_id=\"$client_id\"");
        $sth->execute() or print "error while prepareing query: $DBI::errstr\n";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
		push @vigilada_redes, [ @$ip_ref ];
        }
	$sth->finish();
        $dbh->disconnect;
        return @vigilada_redes;
}

sub check_for_reserved_range {
	my ( $client_id,$red_num ) = @_;
	my $ip_ref;
	my @ranges;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT red_num FROM ranges WHERE red_num = \"$red_num\" AND client_id=\"$client_id\"");
        $sth->execute() or print "error while prepareing query: $DBI::errstr\n";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
		push @ranges, [ @$ip_ref ];
        }
	$sth->finish();
        $dbh->disconnect;
        return @ranges;
}

sub print_help {
	print "\nusage: ip_update_gestioip.pl [OPTIONS...]\n\n";
	print "-t, --test		testing mode - no database changes would be made (needs option -v)\n";
	print "-v, --verbose 		verbose\n";
	print "-V, --Version 		print version and exit\n";
	print "-l, --log=logfile	logfile\n";
	print "-d, --disable_audit	disable audit\n";
	print "-m, --mail		send the result by mail (mail_destinatarios)\n";
	print "-h, --help		help\n\n";
	print "\n\nconfiguration file: $conf\n\n";
	exit;
}

sub print_version {
	print "\n$0 Version $VERSION\n\n";
	exit 0;
}


sub send_mail {
	my $mailer = Mail::Mailer->new("");
	$mailer->open({	From	=> "$$mail_from",
			To	=> "$$mail_destinatarios",
			Subject	=> "Resultado update BBDD GestioIP DNS"
		     }) or die "error while sending mail: $!\n";
	open (LOG_MAIL,"<$log") or die "can not open log file: $!\n";
	while (<LOG_MAIL>) {
		print $mailer $_ if $_ !~ /$lang_vars{ignorado_message}/;
	}
	print $mailer "\n\n$count_entradas $lang_vars{entries_processed_message} (DNS Timeouts: $count_entradas_dns_timeout)\n";
	print $mailer "\n\n\n\n\n\n\n\n\n--------------------------------\n\n";
	print $mailer "$lang_vars{auto_mail_message}\n";
	$mailer->close;
	close LOG;
}

sub int_to_ip {
        my $ip_int=shift;
        my $ip_bin = ip_inttobin ($ip_int,4);
        my $ip_ad = ip_bintoip ($ip_bin,4);
        return $ip_ad;
}

#sub resolve_ip {
#        my $ip=shift;
#        no strict 'subs';
#        my @h = gethostbyaddr(inet_aton($ip), AF_INET);
#        use strict;
#        return @h;
#}


sub mysql_connection {
    my $dbh = DBI->connect("DBI:mysql:$params{sid_gestioip}:$params{bbdd_host_gestioip}:$params{bbdd_port_gestioip}",$params{user_gestioip},$params{pass_gestioip}) or
    die "Cannot connect: ". $DBI::errstr;
    return $dbh;
}

sub insert_audit_auto {
        my ($client_id,$event_class,$event_type,$event,$update_type_audit,$vars_file) = @_;
	my $user=$ENV{'USER'};
        my $mydatetime=time();
        my $dbh = mysql_connection();
        my $qevent_class = $dbh->quote( $event_class );
        my $qevent_type = $dbh->quote( $event_type );
        my $qevent = $dbh->quote( $event );
        my $quser = $dbh->quote( $user );
        my $qupdate_type_audit = $dbh->quote( $update_type_audit );
        my $qmydatetime = $dbh->quote( $mydatetime );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("INSERT INTO audit_auto (event,user,event_class,event_type,update_type_audit,date,client_id) VALUES ($qevent,$quser,$qevent_class,$event_type,$qupdate_type_audit,$qmydatetime,$qclient_id)") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
}

sub get_red {
        my ( $client_id, $red_num ) = @_;
        my $ip_ref;
        my @values_redes;
        my $dbh = mysql_connection();
        my $qred_num = $dbh->quote( $red_num );
        my $sth = $dbh->prepare("SELECT red, BM, descr, loc, vigilada, comentario, categoria FROM net WHERE red_num=$qred_num  AND client_id=\"$client_id\"") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_redes, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values_redes;
}

sub get_loc_from_redid {
        my ( $client_id, $red_num ) = @_;
        my @values_locations;
        my ( $ip_ref, $red_loc );
        my $dbh = mysql_connection();
        my $qred_num = $dbh->quote( $red_num );
        my $sth = $dbh->prepare("SELECT l.loc FROM locations l, net n WHERE n.red_num = $qred_num AND n.loc = l.id AND n.client_id=\"$client_id\"") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $red_loc = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $red_loc;
}

sub get_host {
        my ( $client_id, $first_ip_int, $last_ip_int ) = @_;
        my @values_ip;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $qfirst_ip_int = $dbh->quote( $first_ip_int );
        my $qlast_ip_int = $dbh->quote( $last_ip_int );
        my $sth = $dbh->prepare("SELECT h.ip, h.hostname, h.host_descr, l.loc, c.cat, h.int_admin, h.comentario, ut.type, h.alive, h.last_response, h.range_id FROM host h, locations l, categorias c, update_type ut WHERE ip BETWEEN $qfirst_ip_int AND $qlast_ip_int AND h.loc = l.id AND h.categoria = c.id AND h.update_type = ut.id AND h.client_id=\"$client_id\" ORDER BY h.ip") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_ip, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values_ip;
}

sub get_host_range {
        my ( $client_id,$first_ip_int, $last_ip_int ) = @_;
        my @values_ip;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $qfirst_ip_int = $dbh->quote( $first_ip_int );
        my $qlast_ip_int = $dbh->quote( $last_ip_int );
        my $sth = $dbh->prepare("SELECT h.ip, h.hostname, h.host_descr, l.loc, c.cat, h.int_admin, h.comentario, ut.type, h.alive, h.last_response, h.range_id FROM host h, locations l, categorias c, update_type ut WHERE ip BETWEEN $qfirst_ip_int AND $qlast_ip_int AND h.loc = l.id AND h.categoria = c.id AND h.update_type = ut.id AND range_id != '-1' AND h.client_id=\"$client_id\" ORDER BY h.ip") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_ip, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values_ip;
}


sub get_cat_id {
        my ( $cat ) = @_;
        my $cat_id;
        my $dbh = mysql_connection();
        my $qcat = $dbh->quote( $cat );
        my $sth = $dbh->prepare("SELECT id FROM categorias WHERE cat=$qcat
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $cat_id = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $cat_id;
}

sub get_utype_id {
        my ( $utype ) = @_;
        my $utype_id;
        my $dbh = mysql_connection();
        my $qutype = $dbh->quote( $utype );
        my $sth = $dbh->prepare("SELECT id FROM update_type WHERE type=$qutype
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $utype_id = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $utype_id;
}

sub update_host_ping_info {
        my ( $client_id,$ip_int, $ping_result) = @_;
        my $dbh = mysql_connection();
        my $qip_int = $dbh->quote( $ip_int );
        my $qmydatetime = $dbh->quote( time() );
        my $alive = $dbh->quote( $ping_result );
        my $sth;
        $sth = $dbh->prepare("UPDATE host SET alive=$alive, last_response=$qmydatetime WHERE ip=$qip_int AND client_id=\"$client_id\"") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub delete_ip {
        my ( $client_id,$first_ip_int, $last_ip_int ) = @_;
        my $dbh = mysql_connection();
        my $qfirst_ip_int = $dbh->quote( $first_ip_int );
        my $qlast_ip_int = $dbh->quote( $last_ip_int );
        my $sth = $dbh->prepare("DELETE FROM host WHERE ip BETWEEN $qfirst_ip_int AND $qlast_ip_int AND client_id=\"$client_id\""
                                ) or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub clear_ip {
        my ( $client_id,$first_ip_int, $last_ip_int ) = @_;
        my $dbh = mysql_connection();
        my $qfirst_ip_int = $dbh->quote( $first_ip_int );
        my $qlast_ip_int = $dbh->quote( $last_ip_int );

        my $sth = $dbh->prepare("UPDATE host SET hostname='', host_descr='', int_admin='n', alive='', last_response='' WHERE ip BETWEEN $qfirst_ip_int AND $qlast_ip_int AND client_id=\"$client_id\""
                                ) or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub insert_ip_mod {
        my ( $client_id,$ip_int, $hostname, $host_descr, $loc, $int_admin, $cat, $comentario, $update_type, $mydatetime, $red_num, $alive  ) = @_;
        my $dbh = mysql_connection();
        my $sth;
        my $qhostname = $dbh->quote( $hostname );
        my $qhost_descr = $dbh->quote( $host_descr );
        my $qloc = $dbh->quote( $loc );
        my $qint_admin = $dbh->quote( $int_admin );
        my $qcat = $dbh->quote( $cat );
        my $qcomentario = $dbh->quote( $comentario );
        my $qupdate_type = $dbh->quote( $update_type );
        my $qmydatetime = $dbh->quote( $mydatetime );
        my $qip_int = $dbh->quote( $ip_int );
        my $qred_num = $dbh->quote( $red_num );
        my $qclient_id = $dbh->quote( $client_id );
        if ( defined($alive) ) {
                my $qalive = $dbh->quote( $alive );
                my $qlast_response = $dbh->quote( time() );
                $sth = $dbh->prepare("INSERT INTO host (ip,hostname,host_descr,loc,red_num,int_admin,categoria,comentario,update_type,last_update,alive,last_response,client_id) VALUES ($qip_int,$qhostname,$qhost_descr,$qloc,$qred_num,$qint_admin,$qcat,$qcomentario,$qupdate_type,$qmydatetime,$qalive,$qlast_response,$qclient_id)"
                                ) or die "Can not execute statement: $dbh->errstr";
        } else {
                $sth = $dbh->prepare("INSERT INTO host (ip,hostname,host_descr,loc,red_num,int_admin,categoria,comentario,update_type,last_update,client_id) VALUES ($qip_int,$qhostname,$qhost_descr,$qloc,$qred_num,$qint_admin,$qcat,$qcomentario,$qupdate_type,$qmydatetime,$qclient_id)"
                                ) or die "Can not execute statement: $dbh->errstr";
        }
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub update_ip_mod {
        my ( $client_id,$ip_int, $hostname, $host_descr, $loc, $int_admin, $cat, $comentario, $update_type, $mydatetime, $red_num, $alive ) = @_;
        my $dbh = mysql_connection();
        my $sth;
        my $qhostname = $dbh->quote( $hostname );
        my $qhost_descr = $dbh->quote( $host_descr );
        my $qloc = $dbh->quote( $loc );
        my $qint_admin = $dbh->quote( $int_admin );
        my $qcat = $dbh->quote( $cat );
        my $qcomentario = $dbh->quote( $comentario );
        my $qupdate_type = $dbh->quote( $update_type );
        my $qmydatetime = $dbh->quote( $mydatetime );
        my $qred_num = $dbh->quote( $red_num );
        my $qip_int = $dbh->quote( $ip_int );
        my $qclient_id = $dbh->quote( $client_id );
        if ( defined($alive) ) {
                my $qalive = $dbh->quote( $alive );
                my $qlast_response = $dbh->quote( time() );
                $sth = $dbh->prepare("UPDATE host SET hostname=$qhostname, host_descr=$qhost_descr, loc=$qloc, int_admin=$qint_admin, categoria=$qcat, comentario=$qcomentario, update_type=$qupdate_type, last_update=$qmydatetime, red_num=$qred_num, alive=$qalive, last_response=$qlast_response WHERE ip=$qip_int AND client_id=$qclient_id"
                                ) or die "Can not execute statement: $dbh->errstr";
        } else {
                $sth = $dbh->prepare("UPDATE host SET hostname=$qhostname, host_descr=$qhost_descr, loc=$qloc, int_admin=$qint_admin, categoria=$qcat, comentario=$qcomentario, update_type=$qupdate_type, last_update=$qmydatetime, red_num=$qred_num WHERE ip=$qip_int AND client_id=$qclient_id"
                                ) or die "Can not execute statement: $dbh->errstr";
        }
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $sth->finish();
        $dbh->disconnect;
}


#sub get_all_range_ids {
#	my ( $client_id ) = @_;
#	my $ip_ref;
#	my @range_ids;
#        my $dbh = mysql_connection();
#        my $sth = $dbh->prepare("SELECT red, BM, red_num, loc FROM net WHERE vigilada=\"y\" AND client_id=\"$client_id\"");
#        $sth->execute() or print "error while prepareing query: $DBI::errstr\n";
#        while ( $ip_ref = $sth->fetchrow_arrayref ) {
#        push @range_ids, [ @$ip_ref ];
#        }
#	$sth->finish();
#        $dbh->disconnect;
#        return @range_ids;
#}

sub count_clients {
        my $val;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT count(*) FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub check_one_client_name {
	my ($client_name) = @_; 
        my $val;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT client FROM clients WHERE client=\"$client_name\"
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_id_one {
	my ($client_name) = @_; 
        my $val;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT id FROM clients
                        ") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement: $dbh->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_id_from_name {
        my ( $client_name ) = @_;
        my $val;
        my $dbh = mysql_connection();
        my $qclient_name = $dbh->quote( $client_name );
        my $sth = $dbh->prepare("SELECT id FROM clients WHERE client=$qclient_name");
        $sth->execute() or  die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_client_entries {
        my ( $client_id ) = @_;
        my @values;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $qclient_id = $dbh->quote( $client_id );
	my $sth;
        $sth = $dbh->prepare("SELECT c.client,ce.phone,ce.fax,ce.address,ce.comment,ce.contact_name_1,ce.contact_phone_1,ce.contact_cell_1,ce.contact_email_1,ce.contact_comment_1,ce.contact_name_2,ce.contact_phone_2,ce.contact_cell_2,ce.contact_email_2,ce.contact_comment_2,ce.contact_name_3,ce.contact_phone_3,ce.contact_cell_3,ce.contact_email_3,ce.contact_comment_3,ce.default_resolver,ce.dns_server_1,ce.dns_server_2,ce.dns_server_3 FROM clients c, client_entries ce WHERE c.id = ce.client_id AND c.id = $qclient_id") or die "Can not execute statement: $sth->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values;
}


sub get_version {
        my $val;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT version FROM global_config");
        $sth->execute() or  die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_host_id_from_ip_int {
        my ( $client_id,$ip_int ) = @_;
        my $val;
        my $dbh = mysql_connection();
        my $qip_int = $dbh->quote( $ip_int );
        my $qclient_id = $dbh->quote( $client_id );
	my $sth;
        $sth = $dbh->prepare("SELECT id FROM host WHERE ip=$qip_int AND client_id=$qclient_id") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub delete_custom_host_column_entry {
        my ( $client_id, $host_id ) = @_;
        my $dbh = mysql_connection();
        my $qhost_id = $dbh->quote( $host_id );
        my $qclient_id = $dbh->quote( $client_id );
	my $sth;
        $sth = $dbh->prepare("DELETE FROM custom_host_column_entries WHERE host_id = $qhost_id AND client_id = $qclient_id") or die "Can not execute statement: $dbh->errstr";
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $sth->finish();
        $dbh->disconnect;
}


__DATA__
