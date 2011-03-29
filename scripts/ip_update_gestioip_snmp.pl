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


# ip_update_gestioip_snmp.pl Version 3.0.0

# script para actualizar la BBDD del sistema GestioIP via SNMP queries

# This scripts synchronizes only the networks of GestioIP with marked "sync"-field
# see documentation for further information (www.gestioip.net)


# Usage: ./ip_update_gestioip_snmp.pl --help

# execute it from cron. Example crontab:
# 30 10 * * * /usr/share/gestioip/bin/ip_update_gestioip_snmp.pl -o -m > /dev/null 2>&1


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
use SNMP;
use SNMP::Info;



my $VERSION="3.0.0";
	 
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

my ( $disable_audit, $test, $verbose, $log, $mail, $help, $version_arg, $community_arg );

GetOptions(
	"verbose!"=>\$verbose,
	"Version!"=>\$version_arg,
#	"test!"=>\$test,
	"log=s"=>\$log,
	"disable_audit!"=>\$disable_audit,
	"community_string=s"=>\$community_arg,
	"mail!"=>\$mail,
	"help!"=>\$help
) or print_help();

my $enable_audit = "1";
$enable_audit = "0" if $test || $disable_audit;

if ( $help ) { print_help(); }
if ( $version_arg ) { print_version(); }
if ( $test && ! $verbose ) { print_help(); }

my %params;

open(VARS,"<$conf") or die "Can no open $conf: $!\n";
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


my $gip_version=get_version();

if ( $VERSION !~ /$gip_version/ ) {
	print "\nScript and GestioIP version are not compatible\n\nGestioIP version: $gip_version - script version: $VERSION\n\n";
	exit;
}

my $lang=$params{lang} || "en";
my $vars_file=$base_dir . "/etc/vars/vars_update_gestioip_" . "$lang";

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

my $lockfile = $base_dir . "/var/run/" . $client_name_conf . "_ip_update_gestioip_snmp.lock";

no strict 'refs';
open($lockfile, '<', $0) or die("Unable to create lock file: $!\n");
use strict;

unless (flock($lockfile, LOCK_EX|LOCK_NB)) {
	print "$0 is already running. Exiting.\n";
	exit(1);
}

my $logfile_name;
if ( $client_count == "1" ) {
        $logfile_name = "ip_update_gestioip_snmp.log";
} else {
        $logfile_name = $client_name_conf . "_ip_update_gestioip_snmp.log";
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


my @global_config = get_global_config("$client_id");
my $mib_dir=$global_config[0]->[3] || "";
my $vendor_mib_dirs=$global_config[0]->[4] || "";

my @vendor_mib_dirs = split(",",$vendor_mib_dirs);
my @mibdirs_array;
foreach ( @vendor_mib_dirs ) {
        my $mib_vendor_dir = $mib_dir . "/" . $_;
        if ( ! -e $mib_vendor_dir ) {
		print LOG "$lang_vars{mib_dir_not_exists}\nexiting\n";
		print "$lang_vars{mib_dir_not_exists}: $mib_vendor_dir\nexiting\n";
		exit 1;
                if ( ! -r $mib_vendor_dir ) {
			print "$lang_vars{mib_dir_not_readable}: $mib_vendor_dir\nexiting\n";
			exit 1;
                }
        }
        push (@mibdirs_array,$mib_vendor_dir);

}

my $mibdirs_ref = \@mibdirs_array;

my $community;
if ( $community_arg ) {
	$community=$community_arg;
} else {
	$community=$params{'snmp_community_string'};
}

my $snmp_version=$params{'snmp_version'};
if ( ! $snmp_version ) {
        print "Please configure parameter \"snmp_version\" in the configuration file\n";
        exit 1;
}
$community=$params{'snmp_community_string'} if $snmp_version ne "3";
$community=$params{'snmp_user_name'} if $snmp_version eq "3";
my $sec_level= "";
my $auth_proto= "";
my $auth_pass= "";
my $priv_proto= "";
my $priv_pass= "";
my $auth_is_key="";
my $priv_is_key="";

if ( $snmp_version eq "3" ) {
	$sec_level= $params{'sec_level'};
	$auth_proto= $params{'auth_proto'};
	$auth_pass= $params{'auth_pass'};
	$priv_proto= $params{'priv_proto'};
	$priv_pass= $params{'priv_pass'};
	if ( ! $sec_level ) {
		print "Please configure parameter \"sec_level\"\n";
		exit 1;
	}
	if ( $sec_level eq "noAuthNoPriv" ) {
		$auth_proto= "";
		$auth_pass= "";
		$priv_proto= "";
		$priv_pass= "";
		$auth_is_key="";
		$priv_is_key="";
	} elsif ( $sec_level eq "authNoPriv" ) {
		$priv_proto= "";
		$priv_pass= "";
		$auth_is_key="";
		$priv_is_key="";
	} elsif ( $sec_level eq "authPriv" ) {
		$auth_is_key="";
		$priv_is_key="";
	} else {
		print "\"sec_level\" must be either noAuthNoPriv, authNoPriv or authPriv\n";
		exit 1;
	}
	
	if ( $sec_level eq "authNoPriv" && ! $auth_proto ) {
		print "Please configure parameter \"auth_proto\"\n";
		exit 1;
	} elsif ( $sec_level eq "authNoPriv" && ! $auth_pass ) {
		print "Please configure parameter \"auth_pass\"\n";
		exit 1;
	} elsif ( $sec_level eq "authPriv" && ! $auth_proto ) {
		print "Please configure parameter \"auth_proto\"\n";
		exit 1;
	} elsif ( $sec_level eq "authPriv" && ! $auth_pass ) {
		print "Please configure parameter \"auth_pass\"\n";
		exit 1;
	} elsif ( $sec_level eq "authPriv" && ! $priv_proto ) {
		print "Please configure parameter \"priv_proto\"\n";
		exit 1;
	} elsif ( $sec_level eq "authPriv" && ! $priv_pass ) {
		print "Please configure parameter \"priv_pass\"\n";
		exit 1;
	}
	my $auth_pass_length=length($auth_pass);
	if ( $sec_level ne "noAuthNoPriv" && $auth_pass_length < 8 ) {
		print "auth_pass must contain at least 8 characters\n";
		exit 1;
	}
	my $priv_pass_length=length($auth_pass);
	if ( $sec_level ne "noAuthNoPriv" && $priv_pass_length < 8 ) {
		print "priv_pass must contain at least 8 characters\n";
		exit 1;
	}
}

		
if ( ! $community ) {
        print "Please configure parameter \"snmp_community_string\"\n" if $snmp_version ne "3";
        print "Please configure parameter \"snmp_user_name\"\n" if $snmp_version eq "3";
        exit 1;
}
my $community_type="Community";
if ( $snmp_version == "3" ) {
        $community_type = "SecName";
}



my $ignore_generic_auto=$params{'ignore_generic_auto'};

my $count_entradas_dns=0;
my $count_entradas_dns_timeout=0;

print LOG "\n######## Update via SNMP ($mydatetime) ########\n\n";
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
	my $audit_type="44";
	my $audit_class="1";
	my $update_type_audit="3";
	my $event="---";
	insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
}


my @client_entries=get_client_entries("$client_id");
my $default_resolver = $client_entries[0]->[20];
my @dns_servers =("$client_entries[0]->[21]","$client_entries[0]->[22]","$client_entries[0]->[23]");

my %predef_host_columns=get_predef_host_column_all_hash("$client_id");

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
	my ( $ip_int, $ip_bin, $pm, $res, $pid, $ip );
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

	my $utype="snmp";
	my $ip_hash = get_host_hash_id_key("$client_id","$red_num");

	my $red_loc = get_loc_from_redid("$client_id","$red_num");
	my $red_loc_id = get_loc_id("$client_id","$red_loc");

	for (my $i = $first_ip_int; $i <= $last_ip_int; $i++) {

		my $exit=0;
		my $node=int_to_ip($i);
		my $node_id=get_host_id_from_ip("$client_id","$node") || "";
		
			##fork
			$pid = $pm->start("$node") and next;
				#child

				print "$node: " if $verbose;
				print LOG "$node: ";
				my $utype_db;
				my $device_name_db = "";
				$utype_db=$ip_hash->{$node_id}[7] if $node_id;
				$device_name_db=$ip_hash->{$node_id}[1] if $node_id;
				$device_name_db = "" if ! $device_name_db;
				my $range_id=$ip_hash->{"$node_id"}[10];
				$utype_db = "---" if ! $utype_db;
				if ( $utype_db eq "man" ) {
					print "update type: $utype_db - $lang_vars{ignorado_message}\n" if $verbose;
					print LOG "update type: $utype_db - $lang_vars{ignorado_message}\n";
					$exit = 1;
					$pm->finish($exit); # Terminates the child process
				}

				my $device_type="";
				my $device_vendor="";
				my $device_serial="";
				my $device_contact="";
				my $device_name="";
				my $device_location="";
				my $device_descr="";
				my $device_forwarder="";
				my $device_os="";
				my $device_cat="-1";

				my $mydatetime = time();
				my $new_host = "0";
				my $snmp_info_connect = "1";
				my $snmp_connect = "1";

#				my $bridge = new SNMP::Info ( 
#							AutoSpecify => 1,
#							Debug       => 0,
#							DestHost    => $node,
#							$community_type   => $community,
#							Version     => $snmp_version,
#                                               		MibDirs     => $mibdirs_ref,
#	#						Timeout	    => 20000
#							);

				 my $bridge=create_snmp_info_session("$client_id","$node","$community","$community_type","$snmp_version","$auth_pass","$auth_proto","$auth_is_key","$priv_proto","$priv_pass","$priv_is_key","$sec_level",$mibdirs_ref);


				if ( ! defined($bridge) ) {
	#				print "SNMP::INFO: $lang_vars{can_not_connect_message}<br>\n";
	#				$exit = 1;
	#				$pm->finish($exit); # Terminates the child process
				} else {

					$snmp_info_connect ="0";
					$device_type=$bridge->model() || "";
					$device_type = "" if $device_type =~ /enterprises\.\d/;
					$device_vendor=$bridge->vendor() || "";
					$device_serial=$bridge->serial() || "";
					$device_contact=$bridge->contact() || "";
					$device_name=$bridge->name() || "";
					$device_location=$bridge->location() || "";
					$device_descr=$bridge->description() || "";
					$device_forwarder=$bridge->ipforwarding() || "";
					$device_os="";
				}


					
#				my $session = new SNMP::Session(
#								Version => $snmp_version,
#								DestHost => $node,
#								$community_type   => $community,
#								UseSprintValue => 1,
#	#							Timeout	    => 20000
#								);

				my $session=create_snmp_session("$client_id","$node","$community","$community_type","$snmp_version","$auth_pass","$auth_proto","$auth_is_key","$priv_proto","$priv_pass","$priv_is_key","$sec_level");

				if ( defined $session ) {
					no strict 'subs';	
					my $vars = new SNMP::VarList([sysDescr,0],
								[sysName,0],
								[sysContact,0],
								[sysLocation,0]);
					use strict 'subs';

					my @values = $session->get($vars);

					if ( ! ($session->{ErrorStr}) ) {

						$snmp_connect = "0";

						$device_descr = $values[0];
						$device_name = $values[1];
						$device_contact = $values[2];
						$device_location = $values[3];
						
		
						
						if ( $device_descr =~ /ubuntu/i ) {
							$device_os = "ubuntu";
						} elsif ( $device_descr =~ /debian/i ) {
							$device_os = "debian";
						} elsif ( $device_descr =~ /suse/i ) {
							$device_os = "suse";
						} elsif ( $device_descr =~ /fedora/i ) {
							$device_os = "fedora";
						} elsif ( $device_descr =~ /redhat/i ) {
							$device_os = "redhat";
						} elsif ( $device_descr =~ /centos/i ) {
							$device_os = "centos";
						} elsif ( $device_descr =~ /turbolinux/i ) {
							$device_os = "turbolinux";
						} elsif ( $device_descr =~ /slackware/i ) {
							$device_os = "slackware";
						} elsif ( $device_descr =~ /linux/i ) {
							$device_os = "linux";
						} elsif ( $device_descr =~ /freebsd/i ) {
							$device_os = "freebsd";
						} elsif ( $device_descr =~ /netbsd/i ) {
							$device_os = "netbsd";
						} elsif ( $device_descr =~ /netware/i ) {
							$device_os = "netware";
						} elsif ( $device_descr =~ /openbsd/i ) {
							$device_os = "openbsd";
						} elsif ( $device_descr =~ /solaris/i || $device_descr =~ /sunos/i ) {
							$device_os = "solaris";
						} elsif ( $device_descr =~ /unix/i ) {
							$device_os = "unix";
						} elsif ( $device_descr =~ /windows/i ) {
							$device_os = "windows_server";
						}

						my @vendors=("aficio|ricoh","apple","aruba","adtran","allied","apc","altiga","arista","asante","avocent","axis","barracuda","billion","belair","bluecoat","borderware","brother","broadcom","brocade","calix","cyclades","canon","checkpoint","cisco","cyberoam","dell","dialogic","eci telecom","edgewater","emc","emerson","enterasys","epson","extreme","f5","fluke","fortinet","foundry","h3c","hp|hewlett.?packard","ibm","juniper","proxim","kodak","konica","lancom","alcatel|lucent","lexmark","linksys","lifesize","microsoft","minolta","motorola","netapp","netgear","nokia","nortel","novell","optibase","ovislink","panasonic","passport","palo.?alto","phaser","polycom","qnap","radvision","radware","realtek","riverstone","samsung","siemens","smc","sonicwall","stonesoft","sony","symantec","sun","tandberg","tippingpoint","toplayer","vegastream","vyatta","watchguard","websense","xerox","zyxel");

						foreach ( @vendors ) {
							my $vendor=$_;
							if ( $device_descr =~ /(${vendor}\s)/i ) {
								if ( $device_descr =~ /(ibm.+aix)/i ) {
									$device_vendor = "ibm";
									$device_os = "aix";
								} elsif ( $device_descr =~ /(ibm.+os2)/i ) {
									$device_vendor = "ibm";
									$device_os = "os2";
								} elsif ( $device_descr =~ /(aficio|ricoh)/i ) {
									$device_vendor = "ricoh";
									if ( $device_descr =~ /printer/i ) {
										my $new_cat=get_cat_id("$client_id","printer");
										$device_cat = "$new_cat" if $new_cat;
									}
								} elsif ( $device_descr =~ /(hp\s|hewlett.?packard)/i ) {
									$device_vendor = "hp";
									if ( $device_descr =~ /jet/i ) {
										my $new_cat=get_cat_id("$client_id","printer");
										$device_cat = "$new_cat" if $new_cat;
									}
								} elsif ( $device_descr =~ /(alcatel|lucent)/i ) {
									$device_vendor = "alcatel-lucent";
								} elsif ( $device_descr =~ /(palo.?alto)/i ) {
									$device_vendor = "paloalto";
								} elsif ( $device_descr =~ /(microsoft|windows)/i ) {
									$device_os = "windows";
								} elsif ( $device_descr =~ /cyclades/i ) {
									$device_vendor = "avocent";
								} elsif ( $device_descr =~ /orinoco/i ) {
									$device_vendor = "alcatel-lucent";
								} elsif ( $device_descr =~ /phaser/i ) {
									$device_vendor = "xerox";
								} elsif ( $device_descr =~ /minolta/i ) {
									$device_vendor = "konica";
								} elsif ( $device_descr =~ /check.?point/i ) {
									$device_vendor = "checkpoint";
								} elsif ( $device_descr =~ /top.?layer/i ) {
									$device_vendor = "toplayer";
								} else {
									$device_vendor = $vendor;
								}
							} 
						}
					}
				} else {
					print "SNMP $lang_vars{can_not_connect_message} (1)\n" if $verbose;
					print LOG "SNMP $lang_vars{can_not_connect_message}\n";
				}

				if ( ( $snmp_info_connect == "1" && $snmp_connect == "1" ) ) {
					print "$lang_vars{can_not_connect_message} (2)\n" if $verbose;
					print LOG "$lang_vars{can_not_connect_message}\n";
					$exit = "1";
					$pm->finish($exit); # Terminates the child process
				}

				$device_descr = "" if $device_descr =~ /(unknown|configure)/i;
				$device_contact = "" if $device_contact =~ /(unknown|configure)/i;
				$device_location = "" if $device_location =~ /(unknown|configure)/i;
				$device_name = "unknown" if $device_name =~ /(localhost|DEFAULT SYSTEM NAME)/i;
				$device_vendor = "" if $device_vendor =~ /(unknown)/i;
				$device_contact =~ s/^"//;
				$device_contact =~ s/"$//;
				$device_name =~ s/^"//;
				$device_name =~ s/"$//;
				$device_location =~ s/^"//;
				$device_location =~ s/"$//;

				my $device_name_dns = "";
				if ( ! $node_id && ! $device_name ) {

					my $res_dns;

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

					my $ptr_query;
					my $dns_error="";
					if ( $node =~ /\w+/ ) {
						$ptr_query = $res_dns->query("$node");

						if ($ptr_query) {
							foreach my $rr ($ptr_query->answer) {
								next unless $rr->type eq "PTR";
								$device_name_dns = $rr->ptrdname;
							}
						} else {
							$dns_error = $res_dns->errorstring;
						}
					}


					$node =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
					my $generic_auto = "$2-$3-$4|$4-$3-$2";
					if ( $device_name_dns =~ /$generic_auto/ && $ignore_generic_auto eq "yes" ) {
						$device_name_dns = "unknown";
					}
					$device_name=$device_name_dns if $device_name_db eq "unknown";
				}

				if ( ! $device_name_dns ) {
					$device_name = "unknown" if $device_name =~ /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
				} else {
					$device_name = "" if $device_name =~ /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
				}

				my $hostname_update="0";

				if ( ! $node_id && $device_name ) {
					$device_name =~ s/\s/_/g;
					insert_ip_mod("$client_id","$i","$device_name","","$red_loc_id","n","$device_cat","","-1","$mydatetime","$red_num");
					$new_host = "1";
					$node_id=get_last_host_id("$client_id");
					print LOG "$lang_vars{host_anadido_message}: $device_name";
					print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
				} elsif ( ! $node_id && $device_name_dns ) {
					insert_ip_mod("$client_id","$i","$device_name_dns","","$red_loc_id","n","$device_cat","","-1","$mydatetime","$red_num");
					$new_host = "1";
					$node_id=get_last_host_id("$client_id");
					print "$lang_vars{host_anadido_message}: $device_name_dns" if $verbose;
					print LOG "$lang_vars{host_anadido_message}: $device_name_dns";
				} elsif ( ! $node_id && $device_type ) {
					$device_type =~ /^(.+)\s*/;
					my $device_name = $1;
					insert_ip_mod("$client_id","$i","$device_name","","$red_loc_id","n","$device_cat","","-1","$mydatetime","$red_num");
					$new_host = "1";
					print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
					print LOG "$lang_vars{host_anadido_message}: $device_name";
					$node_id=get_last_host_id("$client_id");
				} elsif ( ! $node_id && $device_vendor ) {
					$device_vendor =~ /^(.+)\s*/;
					my $device_name = $1;
					insert_ip_mod("$client_id","$i","$device_name","","$red_loc_id","n","$device_cat","","-1","$mydatetime","$red_num");
					$new_host = "1";
					print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
					print LOG  "$lang_vars{host_anadido_message}: $device_name";
					$node_id=get_last_host_id("$client_id");
				} elsif ( ! $node_id ) {
					$exit = 1;
					print LOG " $lang_vars{no_device_name_message} - $lang_vars{ignorado_message}\n";
					print " $lang_vars{no_device_name_message} - $lang_vars{ignorado_message}\n" if $verbose;
					$pm->finish($exit); # Terminates the child process
				} elsif ( $node_id  &&  $device_name_db eq "unknown" && $device_name && $device_name ne "unknown" ) {
						update_host_hostname("$client_id","$node_id","$device_name");
						$hostname_update="1";
				} elsif ( $node_id && $range_id != "-1" && ! $device_name_db ) {
					if ( $device_name ) {
						update_host_hostname("$client_id","$node_id","$device_name");
						print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
						print LOG "$lang_vars{host_anadido_message}: $device_name";
						$new_host = "1";
					} elsif ( $device_name_dns ) {
						update_host_hostname("$client_id","$node_id","$device_name_dns");
						print "$lang_vars{host_anadido_message}: $device_name_dns" if $verbose;
						print LOG "$lang_vars{host_anadido_message}: $device_name_dns";
						$new_host = "1";
					} elsif ( $device_type ) {
						$device_type =~ /^(.+)\s*/;
						my $device_name = $1;
						update_host_hostname("$client_id","$node_id","$device_name");
						print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
						print LOG "$lang_vars{host_anadido_message}: $device_name";
						$new_host = "1";
					} elsif ( $device_vendor ) {
						$device_vendor =~ /^(.+)\s*/;
						my $device_name = $1;
						update_host_hostname("$client_id","$node_id","$device_name");
						print "$lang_vars{host_anadido_message}: $device_name" if $verbose;
						print LOG  "$lang_vars{host_anadido_message}: $device_name";
						$new_host = "1";
					} else {
						update_host_hostname("$client_id","$node_id","unknown");
						print "$lang_vars{host_anadido_message}: unknown" if $verbose;
						print LOG "$lang_vars{host_anadido_message}: unknown";
						$new_host = "1";
					}
				}

				my $entry;
				my $audit_entry = "";
				my $audit_entry_cc = "";
				my $audit_entry_cc_new = "";
				my $update = "0";

				while ( my ($key, $value) = each(%predef_host_columns) ) {
					my $pc_id;
					my $cc_id = get_custom_host_column_id_from_name_client("$client_id","$key") || "-1"; 
					next if $cc_id eq "-1";

					if ( $key eq "vendor" ) {
						$entry = $device_vendor;
					} elsif ( $key eq "model" ) {
						$entry = $device_type;
					} elsif ( $key eq "contact" ) {
						$entry = $device_contact;
					} elsif ( $key eq "serial" ) {
						$entry = $device_serial;
					} elsif ( $key eq "device_descr" ) {
						$entry = $device_descr;
					} elsif ( $key eq "device_name" ) {
						$entry = $device_name;
						$entry = "" if $device_name eq "unknown";
					} elsif ( $key eq "device_loc" ) {
						$entry = $device_location;
					} elsif ( $key eq "OS" ) {
						$entry = $device_os;
					} else {
						$entry = "";
					}


					if ( $entry ) {
						$pc_id=$predef_host_columns{$key}[0];

						my @cc_entry_host=();
						my $cc_entry_host=get_custom_host_column_entry_complete("$client_id","$node_id","$cc_id") || "";

						if ( @{$cc_entry_host}[0] ) {
							my $entry_db=@{$cc_entry_host}[0]->[0];
							$entry_db=~s/^\*//;
							$entry_db=~s/\*$//;
							if ( $entry_db ne $entry ) {
								update_custom_host_column_value_host("$client_id","$cc_id","$pc_id","$node_id","$entry");
								if ( $audit_entry_cc ) {
									$audit_entry_cc = $audit_entry_cc . "," . $entry;
								} else {
									$audit_entry_cc = $entry;
								}
								if ( $audit_entry_cc_new ) {
									$audit_entry_cc_new = $audit_entry_cc . "," . @{$cc_entry_host}[0]->[0];
								} else {
									$audit_entry_cc_new = @{$cc_entry_host}[0]->[0];
								}
								$update="2";
							} else {

								if ( $audit_entry_cc ) {
									$audit_entry_cc = $audit_entry_cc . "," . $entry;
								} else {
									$audit_entry_cc = $entry;
								}
								if ( $audit_entry_cc_new ) {
									$audit_entry_cc_new = $audit_entry_cc_new . "," . @{$cc_entry_host}[0]->[0];
								} else {
									$audit_entry_cc_new = @{$cc_entry_host}[0]->[0];
								}
								
							}
						} else {
							insert_custom_host_column_value_host("$client_id","$cc_id","$pc_id","$node_id","$entry");
							if ( $audit_entry_cc ) {
								$audit_entry_cc = $audit_entry_cc . ",---";
							} else {
								$audit_entry_cc = "---";
							}
							if ( $audit_entry_cc_new ) {
								$audit_entry_cc_new = $audit_entry_cc_new . "," . $entry;
							} else {
								$audit_entry_cc_new = $entry;
							}
							$update="1" if $update != "2";
						}
					}
				}


				if ( $hostname_update == "1" && $new_host == "0" ) { 
					print "$lang_vars{host_updated_message}: $device_name" if $verbose;
					print LOG "$lang_vars{host_updated_message}: $device_name";
					print LOG ", " if $update != "0";
				}
				if ( $update == "1" && $new_host == "0" ) {
					print ", " if $hostname_update == "1" && $verbose;
					print LOG ", " if $hostname_update == "1";
					print "$lang_vars{cc_updated_message}" if $verbose;
					print LOG "$lang_vars{cc_updated_message}";
				} elsif ( $update == "0" && $new_host != "1" && $hostname_update == "0" ) {
					print "$lang_vars{no_changes_message}" if $verbose;
					print LOG "$lang_vars{no_changes_message}";
				} elsif ( $update == "2" && $new_host != "1" ) {
					print ", " if $hostname_update == "1" && $verbose;
					print LOG ", " if $hostname_update == "1";
					print "$lang_vars{cc_updated_message}" if $verbose;
					print LOG "$lang_vars{cc_updated_message}";
				}

				print LOG "\n";
				print "\n" if $verbose;
	#			print " - DEVICE TYPE: $device_type - VENDOR: $device_vendor - SERIAL: $device_serial - CONTACT: $device_contact - NAME: $device_name - LOC: $device_location - DESCR: $device_descr - FORWARDER: $device_forwarder <br>";

				if ( $new_host == "1" ) {
					my $audit_type="15";
					my $audit_class="1";
					my $update_type_audit="3";
					$red_loc = "---" if $red_loc eq "NULL";
					my $event="$node: $device_name,---,$red_loc,n,---,---,$utype,$audit_entry";
					insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
				} elsif ( $update == "1" || $update == "2" ) {
					my $audit_type="1";
					my $audit_class="1";
					my $update_type_audit="3";
					my $hostname_audit=$ip_hash->{$node_id}[1] || "---";
					my $host_descr=$ip_hash->{$node_id}[2] || "---";
					my $loc=$ip_hash->{$node_id}[3] || "---";
					my $cat=$ip_hash->{$node_id}[4] || "---";
					my $int_admin=$ip_hash->{$node_id}[5] || "---";
					my $comentario=$ip_hash->{$node_id}[6] || "---";
					my $utype_audit=$ip_hash->{$node_id}[7] || "---";
					$host_descr = "---" if $host_descr eq "NULL";
					$cat = "---" if $cat eq "NULL";
					$loc = "---" if $loc eq "NULL";
					$comentario = "---" if $comentario eq "NULL";
					$utype_audit = "---" if ! $utype_audit;
					$utype_audit = "---" if $utype_audit eq "NULL";
					$hostname_audit = "---" if $hostname_audit eq "NULL";
					my $event="$node: $hostname_audit,$host_descr,$loc,$int_admin,$cat,$comentario,$utype_audit,$audit_entry_cc -> $hostname_audit,$host_descr,$loc,$int_admin,$cat,$comentario,$utype_audit";
					$event=$event . "," . $audit_entry_cc_new if $audit_entry_cc_new;
					insert_audit_auto("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file") if $enable_audit == "1";
				}

				$exit=0;


			$pm->finish($exit); # Terminates the child process

	}

	$pm->wait_all_children;

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
	print "-v, --verbose 		verbose\n";
	print "-V, --Version		print version and exit\n";
	print "-l, --log=logfile	logfile\n";
	print "-d, --disable_audit	disable auditing\n";
	print "-c, --configuratio_file  configuration to use (default: ./ip_update_gestioip.conf)\n";
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
        my $sth = $dbh->prepare("INSERT IGNORE audit_auto (event,user,event_class,event_type,update_type_audit,date,client_id) VALUES ($qevent,$quser,$qevent_class,$event_type,$qupdate_type_audit,$qmydatetime,$qclient_id)") or die "Can not execute statement: $dbh->errstr";
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
        $sth->execute() or die "Can not execute statement:$sth->errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}


sub get_host_hash_id_key {
        my ( $client_id, $red_num ) = @_;
        my %values_ip;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $qred_num = $dbh->quote( $red_num );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth;
        $sth = $dbh->prepare("SELECT h.id,h.ip, INET_NTOA(h.ip),h.hostname, h.host_descr, l.loc, c.cat, h.int_admin, h.comentario, ut.type, h.alive, h.last_response, h.range_id FROM host h, locations l, categorias c, update_type ut WHERE red_num=$qred_num AND h.loc = l.id AND h.categoria = c.id AND h.update_type = ut.id AND h.client_id = $qclient_id") or die "Can not execute statement:<p>$DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";

        my $i=0;
        while ( $ip_ref = $sth->fetchrow_hashref ) {
                my $hostname = $ip_ref->{'hostname'} || "";
                my $range_id = $ip_ref->{'range_id'} || "";
#               next if ! $hostname;
                my $id = $ip_ref->{'id'};
                my $ip_int = $ip_ref->{'ip'};
                my $ip = $ip_ref->{'INET_NTOA(h.ip)'};
                my $host_descr = $ip_ref->{'host_descr'} || "";
                my $loc = $ip_ref->{'loc'} || "";
                my $cat = $ip_ref->{'cat'} || "";
                my $int_admin = $ip_ref->{'int_admin'} || "";
                my $comentario = $ip_ref->{'comentario'} || "";
                my $update_type = $ip_ref->{'type'} || "NULL";
                my $alive = $ip_ref->{'alive'};
                my $last_response = $ip_ref->{'last_response'} || "";
                push @{$values_ip{$id}},"$ip","$hostname","$host_descr","$loc","$cat","$int_admin","$comentario","$update_type","$alive","$last_response","$range_id";
        }

        $dbh->disconnect;
        return \%values_ip;
}

sub get_loc_id {
        my ( $client_id, $loc ) = @_;
        my $loc_id;
        my $dbh = mysql_connection();
        my $qloc = $dbh->quote( $loc );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("SELECT id FROM locations WHERE loc=$qloc AND ( client_id = $qclient_id OR client_id = '9999' )
                        ") or die "select $DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        $loc_id = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $loc_id;
}

sub get_host_id_from_ip {
        my ( $client_id,$ip ) = @_;
        my $val;
        my $dbh = mysql_connection();
        my $qip = $dbh->quote( $ip );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("SELECT id FROM host WHERE ip=INET_ATON($qip) AND client_id=$qclient_id");
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        $val = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $val;
}

sub get_last_host_id {
        my ( $client_id ) = @_;
        my $id;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT id FROM host ORDER BY (id+0) desc
                        ") or die "select $DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        $id = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $id;
}

sub update_host_hostname {
        my ( $client_id, $host_id, $hostname ) = @_;
        my $dbh = mysql_connection();
        my $qhost_id = $dbh->quote( $host_id );
        my $qhostname = $dbh->quote( $hostname );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("UPDATE host SET hostname=$qhostname WHERE id=$qhost_id AND client_id=$qclient_id
                        ") or die "update $DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        $sth->finish();
        $dbh->disconnect;
}


sub get_custom_host_column_id_from_name_client {
        my ( $client_id, $column_name ) = @_;
        my $cc_id;
        my $dbh = mysql_connection();
        my $qcolumn_name = $dbh->quote( $column_name );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("SELECT id FROM custom_host_columns WHERE name=$qcolumn_name AND ( client_id = $qclient_id OR client_id = '9999' )
                        ") or die "select $DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        $cc_id = $sth->fetchrow_array;
        $sth->finish();
        $dbh->disconnect;
        return $cc_id;
}

sub get_custom_host_column_entry_complete {
        my ( $client_id, $host_id, $ce_id ) = @_;
        my @values;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $qhost_id = $dbh->quote( $host_id );
        my $qce_id = $dbh->quote( $ce_id );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("select distinct cce.entry,cce.cc_id from custom_host_column_entries cce WHERE cce.host_id = $qhost_id AND cce.cc_id = $qce_id AND cce.client_id = $qclient_id
                        ") or die "select $DBI::errstr";
        $sth->execute() or die "Can not execute statement: $DBI::errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
                push @values, [ @$ip_ref ];
        }
        $sth->finish();
        $dbh->disconnect;
        return \@values;
}

sub update_custom_host_column_value_host {
        my ( $client_id, $cc_id, $pc_id, $host_id, $entry ) = @_;
        my $dbh = mysql_connection();
        my $qcc_id = $dbh->quote( $cc_id );
        my $qpc_id = $dbh->quote( $pc_id );
        my $qhost_id = $dbh->quote( $host_id );
        my $qentry = $dbh->quote( $entry );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("UPDATE custom_host_column_entries SET cc_id=$qcc_id,entry=$qentry WHERE pc_id=$qpc_id AND host_id=$qhost_id") or die "Can not execute statement:<p>$DBI::errstr";
        $sth->execute() or die "Can not execute statement:<p>$DBI::errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub insert_custom_host_column_value_host {
        my ( $client_id, $cc_id, $pc_id, $host_id, $entry ) = @_;
        my $dbh = mysql_connection();
        my $qcc_id = $dbh->quote( $cc_id );
        my $qpc_id = $dbh->quote( $pc_id );
        my $qhost_id = $dbh->quote( $host_id );
        my $qentry = $dbh->quote( $entry );
        my $qclient_id = $dbh->quote( $client_id );
        my $sth = $dbh->prepare("INSERT INTO custom_host_column_entries (cc_id,pc_id,host_id,entry,client_id) VALUES ($qcc_id,$pc_id,$qhost_id,$qentry,$qclient_id)") or die "Can not execute statement:<p>$DBI::errstr";
        $sth->execute() or die "Can not execute statement:<p>$DBI::errstr";
        $sth->finish();
        $dbh->disconnect;
}

sub get_predef_host_column_all_hash {
        my ( $client_id ) = @_;
        my $dbh = mysql_connection();
        my $ip_ref;
        my %values;
        my $sth = $dbh->prepare("SELECT id,name FROM predef_host_columns WHERE id != '-1'
                        ") or die "select $DBI::errstr";
        $sth->execute() or die "Can not execute statement:<p>$DBI::errstr";
        while ( $ip_ref = $sth->fetchrow_hashref ) {
                my $id = $ip_ref->{id};
                my $name = $ip_ref->{name};
                push @{$values{$name}},"$id";
        }
        $sth->finish();
        $dbh->disconnect;
        return %values;
}

sub get_global_config {
        my ( $client_id ) = @_;
        my @values_config;
        my $ip_ref;
        my $dbh = mysql_connection();
        my $sth = $dbh->prepare("SELECT version, default_client_id, confirmation, mib_dir, vendor_mib_dirs FROM global_config") or die "Can not execute statement:<p>$DBI::errstr";
        $sth->execute() or die "Can not execute statement:<p>$DBI::errstr";
        while ( $ip_ref = $sth->fetchrow_arrayref ) {
        push @values_config, [ @$ip_ref ];
        }
        $dbh->disconnect;
        return @values_config;
}


sub create_snmp_session {
	my ($client_id,$node,$community,$community_type,$snmp_version,$auth_pass,$auth_proto,$auth_is_key,$priv_proto,$priv_pass,$priv_is_key,$sec_level) = @_;

	my $session;
	my $error;

	if ( $snmp_version == "1" || $snmp_version == "2" ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						UseSprintValue => 1,
						Verbose => 1
						);
	} elsif ( $snmp_version == "3" && $community && ! $auth_proto && ! $priv_proto ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && ! $auth_is_key && ! $priv_proto ) {
		$session = new SNMP::Session(DestHost => $node,
						Debug=>1,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthPass => $auth_pass,
						AuthProto => $auth_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $auth_is_key && ! $priv_proto ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthMasterKey => $auth_pass,
						AuthProto => $auth_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && ! $auth_is_key && ! $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthPass => $auth_pass,
						AuthProto => $auth_proto,
						PrivPass => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && $auth_is_key && ! $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthMasterKey => $auth_pass,
						AuthProto => $auth_proto,
						PrivPass => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && ! $auth_is_key && $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthPass => $auth_pass,
						AuthProto => $auth_proto,
						PrivMasterKey => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && $auth_is_key && $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthMasterKey => $auth_pass,
						AuthProto => $auth_proto,
						PrivMasterKey => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} else {
		print "Can not determine SecLevel\n";
		exit 1;
	}

	
#	print "$lang_vars{can_not_connect_message}\n" unless
#  (defined $session);

	return $session;
}


sub create_snmp_info_session {
	my ($client_id,$node,$community,$community_type,$snmp_version,$auth_pass,$auth_proto,$auth_is_key,$priv_proto,$priv_pass,$priv_is_key,$sec_level,$mibdirs_ref,$vars_file) = @_;

#	my %lang_vars = $self->_get_vars("$vars_file");
	my $session;
	my $error;

	if ( $snmp_version == "1" || $snmp_version == "2" ) {
		$session = new SNMP::Info (
			AutoSpecify => 1,
			Debug       => 0,
			DestHost    => $node,
			$community_type => $community,
			Version     => $snmp_version,
			MibDirs     => $mibdirs_ref,
			);

	} elsif ( $snmp_version == "3" && $community && ! $auth_proto && ! $priv_proto ) {

		$session = new SNMP::Info (
			AutoSpecify => 1,
			Debug       => 0,
			DestHost    => $node,
			$community_type => $community,
			Version     => $snmp_version,
			SecLevel => $sec_level,
			MibDirs     => $mibdirs_ref,
			);

	} elsif ( $snmp_version == "3" && $auth_proto && ! $auth_is_key && ! $priv_proto ) {

		$session = new SNMP::Info (
			AutoSpecify => 1,
			Debug       => 0,
			DestHost    => $node,
			$community_type => $community,
			Version     => $snmp_version,
			SecLevel => $sec_level,
			AuthPass => $auth_pass,
			AuthProto => $auth_proto,
			MibDirs     => $mibdirs_ref,
			);
	} elsif ( $snmp_version == "3" && $auth_proto && $auth_is_key && ! $priv_proto ) {

		$session = new SNMP::Info (
			AutoSpecify => 1,
			Debug       => 0,
			DestHost    => $node,
			$community_type => $community,
			Version     => $snmp_version,
			SecLevel => $sec_level,
			AuthLocalizedKey => $auth_pass,
			AuthProto => $auth_proto,
			MibDirs     => $mibdirs_ref,
			);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && ! $auth_is_key && ! $priv_is_key ) {

		$session = new SNMP::Info (
			AutoSpecify => 1,
			Debug       => 0,
			DestHost    => $node,
			$community_type => $community,
			Version     => $snmp_version,
			SecLevel => $sec_level,
			AuthPass => $auth_pass,
			AuthProto => $auth_proto,
			PrivPass => $priv_pass,
			PrivProto => $priv_proto,
			MibDirs     => $mibdirs_ref,
			);

	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && $auth_is_key && ! $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthMasterKey => $auth_pass,
						AuthProto => $auth_proto,
						PrivPass => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && ! $auth_is_key && $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthPass => $auth_pass,
						AuthProto => $auth_proto,
						PrivMasterKey => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} elsif ( $snmp_version == "3" && $auth_proto && $priv_proto && $auth_is_key && $priv_is_key ) {
		$session = new SNMP::Session(DestHost => $node,
						$community_type => $community,
						Version => $snmp_version,
						SecLevel => $sec_level,
						AuthMasterKey => $auth_pass,
						AuthProto => $auth_proto,
						PrivMasterKey => $priv_pass,
						PrivProto => $priv_proto,
						UseSprintValue => 1
						);
	} else {
		print "Can not determine SecLevel\n";
	}

	
#	print "$lang_vars{can_not_connect_message}\n" unless
#  (defined $session);

	return $session;
}

__DATA__
